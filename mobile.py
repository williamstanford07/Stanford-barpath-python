"""Phone interface; all tracking and analysis execute in Python on the laptop.

Run python mobile.py, then scan the QR displayed on the laptop. Local Wi-Fi only.
"""
import atexit
import base64
import csv
from concurrent.futures import ThreadPoolExecutor
import io
import json
import logging
import math
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import tempfile
import threading
import uuid
import webbrowser

import cv2
from flask import Flask, abort, jsonify, redirect, request, send_file, session as login
import imageio_ffmpeg
import qrcode
from waitress import serve
from session import Session
from rendering import annotate

ROOT = Path(__file__).parent
DATA = Path(tempfile.mkdtemp(prefix='stanford_phone_'))
atexit.register(lambda: shutil.rmtree(DATA, ignore_errors=True))
KEY = secrets.token_urlsafe(24)
app = Flask(__name__, static_folder=None)
app.secret_key = secrets.token_bytes(32)
app.config.update(MAX_CONTENT_LENGTH=250*1024*1024, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Strict')
JOBS = {}
LOCK = threading.Lock()
POOL = ThreadPoolExecutor(max_workers=1)


def local_ip():
    # Route selection only; no connection or video transfer to this address.
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(('192.0.2.1', 80))
        return sock.getsockname()[0]
    except OSError:
        return socket.gethostbyname(socket.gethostname())
    finally:
        sock.close()


@app.before_request
def authorize():
    if request.path == '/' and secrets.compare_digest(request.args.get('key', ''), KEY):
        login['allowed'] = True
        return redirect('/')
    if not login.get('allowed'):
        abort(403, 'Open the private link or QR shown by your laptop.')
    if request.method == 'POST' and request.headers.get('X-BarPath') != '1':
        abort(403)


@app.after_request
def headers(response):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    return response


@app.errorhandler(413)
def too_large(error):
    return jsonify(error='Video is too large. Choose a clip smaller than 250 MB.'), 413


def resize(frame):
    h, w = frame.shape[:2]
    factor = min(1, 960/max(w, h))
    return cv2.resize(frame, (max(2, int(w*factor)//2*2), max(2, int(h*factor)//2*2)))


def job_for(identifier):
    if identifier not in JOBS:
        abort(404)
    return JOBS[identifier]


def open_video(source):
    cap = cv2.VideoCapture(str(source))
    # Apply phone display metadata once, at decoding, in every reading path.
    cap.set(cv2.CAP_PROP_ORIENTATION_AUTO, 1)
    return cap


def rotation_value(value):
    angle = int(value)
    if angle not in (0, 90, 180, 270):
        raise ValueError('Rotation must be 0, 90, 180, or 270 degrees.')
    return angle


def orient(frame, rotation=0):
    codes = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180,
             270: cv2.ROTATE_90_COUNTERCLOCKWISE}
    if rotation in codes:
        frame = cv2.rotate(frame, codes[rotation])
    return resize(frame)


def frame_at(job, index, rotation=0):
    cap = open_video(job['source'])
    try:
        cap.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = cap.read()
        if not ok:
            raise ValueError('Could not read this frame. Choose an earlier frame or an H.264 MP4.')
        return orient(frame, rotation)
    finally:
        cap.release()


@app.get('/')
def index():
    return send_file(ROOT/'phone.html')


@app.get('/phone-qr')
def phone_qr():
    image = qrcode.make(f'http://{local_ip()}:8765/?key={KEY}')
    result = io.BytesIO()
    image.save(result, format='PNG')
    result.seek(0)
    return send_file(result, mimetype='image/png')


@app.post('/upload')
def upload():
    with LOCK:
        if any(j['state'] == 'processing' for j in JOBS.values()):
            return jsonify(error='Wait for the current analysis to finish.'), 409
        if len(JOBS) >= 5:
            return jsonify(error='Five clips are loaded. Use Delete uploaded clips and results to make room.'), 409
    file = request.files.get('video')
    if file is None:
        return jsonify(error='Choose a video.'), 400
    identifier = uuid.uuid4().hex
    folder = DATA/identifier
    folder.mkdir()
    source = folder/'source.video'
    file.save(source)
    cap = open_video(source)
    ok, first = cap.read()
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    if not ok:
        shutil.rmtree(folder)
        return jsonify(error='Cannot decode this video. Try an H.264 MP4; some iPhone HEVC clips need conversion.'), 400
    fps = fps if math.isfinite(fps) and 1 <= fps <= 240 else 30.0
    first = resize(first)
    JOBS[identifier] = dict(source=source, folder=folder, fps=fps, count=max(1, count), state='ready', progress=0)
    return jsonify(id=identifier, frames=max(1, count), fps=fps, width=first.shape[1], height=first.shape[0])


@app.get('/frame/<identifier>/<int:frame>')
def preview(identifier, frame):
    job = job_for(identifier)
    if frame >= job['count']:
        abort(400)
    try:
        image = frame_at(job, frame, rotation_value(request.args.get('rotation', 0)))
    except ValueError as error:
        return jsonify(error=str(error)), 400
    ok, data = cv2.imencode('.jpg', image)
    if not ok:
        abort(500)
    return send_file(io.BytesIO(data.tobytes()), mimetype='image/jpeg')


@app.post('/analyze/<identifier>')
def analyze(identifier):
    job = job_for(identifier)
    options = request.get_json(silent=True) or {}
    try:
        start = int(options.get('start', 0))
        duration = min(60, max(2, float(options.get('seconds', 20))))
        radius = min(960, max(60, int(options.get('radius', 300))))
        markers = options['markers']
        enabled = bool(options.get('depth'))
        if not 0 <= start < job['count'] or not isinstance(markers, dict):
            raise ValueError('Invalid starting frame.')
        rotation = rotation_value(options.get('rotation', 0))
        first = frame_at(job, start, rotation)
        tracking = Session(radius)
        tracking.depth_enabled = enabled
        for name in (['bar', 'hip', 'knee'] if enabled else ['bar']):
            x, y = map(float, markers[name])
            if not math.isfinite(x+y):
                raise ValueError('Invalid marker position.')
            tracking.select(first, name, x, y)
    except (ValueError, KeyError, TypeError, OverflowError) as error:
        return jsonify(error='Check all marker positions. '+str(error)), 400
    with LOCK:
        if any(j['state'] == 'processing' for j in JOBS.values()):
            return jsonify(error='An analysis is already running.'), 409
        job.update(state='processing', progress=0, error=None, report=None)
    POOL.submit(process, job, tracking, first, start, duration, rotation)
    return jsonify(state='processing')


def process(job, tracking, first, start, seconds, rotation=0):
    cap = open_video(job['source'])
    cap.set(cv2.CAP_PROP_POS_FRAMES, start+1)
    avi, mp4 = job['folder']/'clip.avi', job['folder']/'clip.mp4'
    writer = cv2.VideoWriter(str(avi), cv2.VideoWriter_fourcc(*'MJPG'), job['fps'], (first.shape[1], first.shape[0]))
    count = min(int(seconds*job['fps']), 3600, max(0, job['count']-start-1))
    try:
        if not writer.isOpened() or count < 1:
            raise ValueError('Not enough video after this frame, or video export could not start.')
        writer.write(annotate(first, tracking))
        last = first
        for i in range(count):
            ok, frame = cap.read()
            if not ok:
                break
            last = orient(frame, rotation)
            tracking.process(last, (start+i+1)/job['fps'])
            writer.write(annotate(last, tracking))
            with LOCK:
                job['progress'] = round((i+1)/count*90)
        writer.release()
        cap.release()
        cv2.imwrite(str(job['folder']/'path.png'), annotate(last, tracking))
        report = tracking.report()
        report['stopped_on_bar_loss'] = False
        report['tracking_version'] = 'recovery-4'
        report['first_bar_gap_frame'] = next((start+i+1 for i, s in enumerate(tracking.samples)
                                               if s.bar_x is None), None)
        report['first_depth_gap_frame'] = next((start+i+1 for i, s in enumerate(tracking.samples)
                                                 if tracking.depth_enabled and s.hip_x is None), None)
        report['orientation_version'] = 'orientation-3'
        report['manual_rotation_clockwise'] = rotation
        report['ended_with_bar_lost'] = tracking.bar_lost
        (job['folder']/'report.json').write_text(json.dumps(report, indent=2))
        if tracking.samples:
            with (job['folder']/'measurements.csv').open('w', newline='') as handle:
                rows = [s.to_dict() for s in tracking.samples]
                csv_writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                csv_writer.writeheader()
                csv_writer.writerows(rows)
        conversion = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-i', str(avi), '-an',
                                     '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(mp4)],
                                    capture_output=True, timeout=180)
        if conversion.returncode:
            raise ValueError('Analysis completed but MP4 conversion failed. Retry a shorter clip.')
        with LOCK:
            job.update(state='done', progress=100, report=report)
    except Exception as error:
        with LOCK:
            job.update(state='error', error=str(error))
    finally:
        cap.release()
        writer.release()


@app.get('/status/<identifier>')
def status(identifier):
    job = job_for(identifier)
    with LOCK:
        return jsonify({k: job.get(k) for k in ('state', 'progress', 'error', 'report')})


@app.get('/result/<identifier>/<kind>')
def result(identifier, kind):
    job = job_for(identifier)
    names = {'video': 'clip.mp4', 'image': 'path.png', 'csv': 'measurements.csv', 'report': 'report.json'}
    if job['state'] != 'done' or kind not in names:
        abort(404)
    path = job['folder']/names[kind]
    if not path.exists():
        abort(404)
    return send_file(path, as_attachment=request.args.get('download') == '1', download_name='stanford_'+path.name)


if __name__ == '__main__':
    url = f'http://{local_ip()}:8765/?key={KEY}'
    print('\nSTANFORD PHONE MODE\nKeep this window open. Connect your phone to the same Wi-Fi.\n')
    print('Phone link: '+url+'\nOn your laptop, expand Connect phone to scan the QR.\n')
    threading.Timer(1.0, lambda: webbrowser.open('http://127.0.0.1:8765/?key='+KEY)).start()
    serve(app, host='0.0.0.0', port=8765, threads=4)
