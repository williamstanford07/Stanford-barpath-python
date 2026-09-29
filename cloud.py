"""Single-owner hosted entry point. Run one process, with HTTPS at the host."""
import os
import secrets
import shutil
from flask import request, session, redirect, render_template_string, jsonify, abort
from waitress import serve
import mobile

PASSWORD = os.environ.get('BARPATH_PASSWORD', '')
SECRET = os.environ.get('SESSION_SECRET', '')
if len(PASSWORD) < 24 or len(SECRET) < 32:
    raise RuntimeError('Set BARPATH_PASSWORD (24+ characters) and SESSION_SECRET (32+ characters).')
app = mobile.app
app.secret_key = SECRET
app.config['SESSION_COOKIE_SECURE'] = True
LOGIN = '''<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#101010"><title>BarPath · Sign in</title><style>
*{box-sizing:border-box}body{background:#101010;color:#f3f1ed;font:16px/1.5 Arial,Helvetica,sans-serif;max-width:440px;margin:12vh auto;padding:24px}h1{font-size:34px;letter-spacing:-1.5px;border-bottom:2px solid #ed3d43;padding-bottom:18px;margin-bottom:18px}p{color:#aaa9a5}form{margin-top:28px}label{font-size:14px}input,button{width:100%;padding:14px;margin:10px 0;font:inherit;border-radius:4px}input{background:#181818;border:1px solid #444;color:#fff}button{background:#ed3d43;border:0;color:#fff;font-weight:700;cursor:pointer}:focus-visible{outline:2px solid white;outline-offset:3px}.error{color:#ffacac}</style></head>
<body><h1>BarPath</h1><p>Sign in to review your lifts.</p><form method="post" action="/login"><input type="hidden" name="csrf" value="{{csrf}}"><label for="password">Password</label><input id="password" name="password" type="password" autocomplete="current-password" required><button>Open BarPath</button></form><p class="error" role="alert">{{error}}</p></body></html>'''

def cloud_gate():
    if request.path == '/healthz':
        return jsonify(status='ok')
    if request.path == '/phone-qr':
        abort(404)
    if request.path == '/login':
        error = ''
        if request.method == 'POST':
            if not secrets.compare_digest(request.form.get('csrf', ''), session.get('csrf', 'missing')):
                abort(403)
            if secrets.compare_digest(request.form.get('password', ''), PASSWORD):
                session.clear()
                session['allowed'] = True
                return redirect('/')
            error = 'Password did not match.'
        session.setdefault('csrf', secrets.token_urlsafe(32))
        return render_template_string(LOGIN, csrf=session['csrf'], error=error), 401 if error else 200
    if not session.get('allowed'):
        if request.path == '/':
            return redirect('/login')
        return jsonify(error='Sign in again to continue.'), 401

# Run before the local application's authorization check.
app.before_request_funcs[None].insert(0, cloud_gate)

@app.post('/clear-clips')
def clear_clips():
    with mobile.LOCK:
        if any(j['state'] == 'processing' for j in mobile.JOBS.values()):
            return jsonify(error='Wait for analysis to finish before clearing clips.'), 409
        for job in mobile.JOBS.values():
            shutil.rmtree(job['folder'], ignore_errors=True)
        mobile.JOBS.clear()
    return jsonify(ok=True)

if __name__ == '__main__':
    serve(app, host='0.0.0.0', port=int(os.environ.get('PORT', '10000')), threads=4)
