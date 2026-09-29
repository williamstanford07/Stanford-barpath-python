import unittest
from unittest.mock import patch
import cv2
from session import Session
from tracking import Match
from test_core import image


class FixedLineTests(unittest.TestCase):
    def test_line_stays_fixed_and_counts_once_per_crossing(self):
        frame = cv2.cvtColor(image(), cv2.COLOR_GRAY2BGR)
        s = Session()
        s.depth_enabled = True
        for name, point in [('bar',(100,80)),('hip',(100,80)),('knee',(140,130))]:
            s.select(frame,name,*point)
        hip = s.trackers['hip']
        with patch.object(s.trackers['knee'],'update',create=True,side_effect=AssertionError('Knee must not track')):
            for y in [100]*3+[120]*3+[140]*8+[120]*3+[100]*3+[120]*3+[140]*3:
                with patch.object(hip,'update',return_value=Match(100,y,.95)):
                    # Mimic the normal tracker updating its trusted position.
                    hip.point=(100,y)
                    sample=s.process(frame,len(s.samples)/30)
                self.assertEqual(sample.knee_y,130)
        self.assertEqual(s.depth_crossings,2)
        with patch.object(hip,'update',return_value=None):
            s.process(frame,1)
        self.assertFalse(s.depth_armed)
        self.assertTrue(s.depth_lost)
        self.assertEqual(s.depth_crossings,2)
