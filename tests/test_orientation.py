import subprocess
import shutil
import tempfile
import unittest
from pathlib import Path
import cv2
import imageio_ffmpeg
import numpy as np
import mobile
from session import Session


class OrientationTests(unittest.TestCase):
    def test_rotation_and_validation(self):
        frame = np.arange(60*80*3, dtype=np.uint8).reshape(60, 80, 3)
        for angle, turns in [(0, 0), (90, 3), (180, 2), (270, 1)]:
            np.testing.assert_array_equal(mobile.orient(frame, angle), np.rot90(frame, turns))
        with self.assertRaises(ValueError):
            mobile.rotation_value(45)

    def test_metadata_preview_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source = folder/'source.mp4'
            tagged = folder/'tagged.mp4'
            ffmpeg = shutil.which('ffmpeg')
            if not ffmpeg:
                self.skipTest('System ffmpeg required to create rotation metadata fixture')
            subprocess.run([ffmpeg, '-v', 'error', '-f', 'lavfi', '-i',
                            'testsrc2=size=160x120:rate=10', '-t', '2',
                            '-c:v', 'libx264', str(source)], check=True)
            subprocess.run([ffmpeg, '-v', 'error', '-display_rotation', '90',
                            '-i', str(source), '-c', 'copy', str(tagged)], check=True)
            job = dict(source=tagged, folder=folder, fps=10, count=20)
            first = mobile.frame_at(job, 0)
            self.assertEqual(first.shape[:2], (160, 120))
            manual = mobile.frame_at(job, 0, 90)
            self.assertEqual(manual.shape[:2], (120, 160))
            tracking = Session()
            tracking.select(manual, 'bar', 70, 60)
            mobile.process(job, tracking, manual, 0, 2, 90)
            self.assertEqual(job['state'], 'done', job)
            cap = cv2.VideoCapture(str(folder/'clip.mp4'))
            ok, exported = cap.read()
            self.assertTrue(ok)
            self.assertEqual(exported.shape, manual.shape)
            self.assertEqual(int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), 20)
            cap.release()
