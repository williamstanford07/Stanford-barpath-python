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
LOGIN = '''<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1">
<title>STANFORD · Sign in</title><style>body{background:#101014;color:#fff;font:18px system-ui;max-width:440px;margin:12vh auto;padding:24px}h1{color:#ff4650}input,button{box-sizing:border-box;width:100%;padding:16px;margin:12px 0;font:inherit}button{background:#ff4650;border:0;color:white}p{color:#bbb}</style>
<h1>STANFORD</h1><p>Your private Python squat tracker.</p><form method="post" action="/login"><input type="hidden" name="csrf" value="{{csrf}}"><label for="password">Access password</label><input id="password" name="password" type="password" autocomplete="current-password" required><button>Open tracker</button></form><p>{{error}}</p>'''

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
