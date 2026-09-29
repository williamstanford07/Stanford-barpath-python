"""Synthetic checks; these do not establish accuracy on actual lifting footage."""
import unittest
import tempfile
from pathlib import Path
import cv2
import numpy as np
from tracking import PointTracker
from session import Session
from analysis import Sample, depth_estimate, summarize
from rendering import annotate


def image(x=100, y=80, hidden=False):
    canvas = np.full((300, 420), 25, dtype=np.uint8)
    if not hidden:
        cv2.rectangle(canvas, (x-10, y-10), (x+10, y+10), 170, -1)
        cv2.circle(canvas, (x-4, y-3), 5, 250, -1)
        cv2.line(canvas, (x-8, y+7), (x+8, y), 50, 3)
    return canvas


class CoreTests(unittest.TestCase):
    def test_large_motion_and_recovery(self):
        tracker = PointTracker()
        tracker.select(image(), 100, 80)
        for x, y in [(104, 88), (108, 160), (110, 235)]:
            match = tracker.update(image(x, y))
            self.assertIsNotNone(match)
            self.assertLess(abs(match.x-x)+abs(match.y-y), 3)
        self.assertIsNone(tracker.update(image(hidden=True)))
        self.assertIsNotNone(tracker.update(image(112, 230)))

    def test_low_texture(self):
        with self.assertRaises(ValueError):
            PointTracker().select(image(hidden=True), 100, 80)

    def test_depth(self):
        self.assertEqual(depth_estimate((10, 100), (50, 80))[0], 'below')
        self.assertEqual(depth_estimate((10, 60), (50, 80))[0], 'above')
        self.assertEqual(depth_estimate((10, 84), (50, 80))[0], 'borderline')
        self.assertEqual(depth_estimate(None, (50, 80))[0], 'unavailable')

    def test_feedback(self):
        samples = [Sample(i/30, 100, 50+4*(20-abs(20-i))) for i in range(41)]
        report = summarize(samples)
        self.assertEqual(report['maximum_drift_px'], 0)
        self.assertTrue(any('returned near' in s for s in report['feedback']))
        samples.append(Sample(2, None, None, tracking_gap=True))
        self.assertEqual(summarize(samples)['missing_frames'], 1)

    def test_file_pipeline_and_video_export(self):
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder)/'source.avi', Path(folder)/'annotated.avi'
            writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*'MJPG'), 30, (420, 300))
            self.assertTrue(writer.isOpened())
            for i in range(50):
                frame = cv2.cvtColor(image(100+i//10, 80+int(100*np.sin(np.pi*i/49))), cv2.COLOR_GRAY2BGR)
                writer.write(frame)
            writer.release()
            cap = cv2.VideoCapture(str(source))
            ok, first = cap.read()
            self.assertTrue(ok)
            session = Session()
            session.select(first, 'bar', 100, 80)
            export = cv2.VideoWriter(str(output), cv2.VideoWriter_fourcc(*'MJPG'), 30, (420, 300))
            self.assertTrue(export.isOpened())
            index = 1
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                session.process(frame, index/30)
                export.write(annotate(frame, session))
                index += 1
            cap.release()
            export.release()
            self.assertFalse(session.bar_lost)
            self.assertGreater(session.report()['vertical_range_px'], 90)
            result = cv2.VideoCapture(str(output))
            self.assertTrue(result.read()[0])
            self.assertEqual(int(result.get(cv2.CAP_PROP_FRAME_COUNT)), 49)
            result.release()
            session.clear()
            self.assertFalse(session.ready())
            self.assertEqual(session.samples, [])


if __name__ == '__main__':
    unittest.main()
