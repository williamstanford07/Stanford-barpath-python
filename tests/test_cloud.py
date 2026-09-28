import io
import time
import unittest
import cv2
from test_core import image
import os
import re
os.environ['BARPATH_PASSWORD'] = 'test-password-for-cloud-validation-only'
os.environ['SESSION_SECRET'] = 'test-session-secret-for-cloud-validation-only'
import cloud
import mobile


class PhoneTests(unittest.TestCase):
    def test_upload_analyze_download(self):
        client = mobile.app.test_client()
        mobile.app.config['SESSION_COOKIE_SECURE'] = False  # Test client uses HTTP.
        self.assertEqual(client.get('/healthz').status_code, 200)
        self.assertEqual(client.get('/').location, '/login')
        self.assertEqual(client.get('/?key='+mobile.KEY).location, '/login')
        self.assertEqual(client.get('/phone-qr').status_code, 404)
        page = client.get('/login')
        csrf = re.search(r'name="csrf" value="([^"]+)"', page.text).group(1)
        self.assertEqual(client.post('/login', data={'password': cloud.PASSWORD}).status_code, 403)
        self.assertEqual(client.post('/login', data={'password': 'wrong', 'csrf': csrf}).status_code, 401)
        self.assertEqual(client.post('/login', data={'password': cloud.PASSWORD, 'csrf': csrf}).status_code, 302)
        page = client.get('/')
        self.assertEqual(page.status_code, 200)
        page.close()
        self.assertEqual(client.post('/upload').status_code, 403)
        source = mobile.DATA/'test_input.avi'
        writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*'MJPG'), 30, (420, 300))
        for i in range(60):
            writer.write(cv2.cvtColor(image(100, 80+i), cv2.COLOR_GRAY2BGR))
        writer.release()
        headers = {'X-BarPath': '1'}
        response = client.post('/upload', headers=headers, data={'video': (io.BytesIO(source.read_bytes()), 'squat.avi')})
        self.assertEqual(response.status_code, 200)
        identifier = response.json['id']
        frame = client.get('/frame/'+identifier+'/0')
        self.assertEqual(frame.status_code, 200)
        frame.close()
        invalid = client.post('/analyze/'+identifier, headers=headers, json={'markers': {}})
        self.assertEqual(invalid.status_code, 400)
        response = client.post('/analyze/'+identifier, headers=headers, json={'markers': {'bar': [100, 80]}, 'seconds': 2})
        self.assertEqual(response.status_code, 200)
        deadline = time.monotonic()+30
        while time.monotonic() < deadline:
            state = client.get('/status/'+identifier).json
            if state['state'] in ('done', 'error'):
                break
            time.sleep(.05)
        self.assertEqual(state['state'], 'done', state)
        self.assertGreater(state['report']['tracked_frames'], 40)
        for kind in ('video', 'image', 'csv', 'report'):
            download = client.get('/result/'+identifier+'/'+kind)
            self.assertEqual(download.status_code, 200)
            self.assertGreater(len(download.data), 10)
            download.close()
        self.assertEqual(client.get('/result/'+identifier+'/secret').status_code, 404)

        self.assertEqual(client.post('/clear-clips').status_code, 403)
        self.assertEqual(client.post('/clear-clips', headers=headers).status_code, 200)
        self.assertEqual(client.get('/result/'+identifier+'/video').status_code, 404)
