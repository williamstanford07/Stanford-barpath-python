import unittest
from unittest.mock import patch
import cv2
from tracking import PointTracker, Match
from session import Session
from test_core import image
from analysis import summarize, Sample

class RecoveryTests(unittest.TestCase):
    def test_projected_depth_points_can_move_closer(self):
        s=Session();s.depth_enabled=True
        frame=cv2.cvtColor(image(),cv2.COLOR_GRAY2BGR)
        s.select(frame,'bar',100,80)
        for name,point in [('hip',(100,100)),('knee',(120,130))]:
            t=PointTracker();t.select(image(),100,80);t.point=point;s.trackers[name]=t
        with patch.object(s.trackers['hip'],'update',return_value=Match(110,110,.9)), patch.object(s.trackers['knee'],'update',return_value=Match(130,110,.9)):
            sample=s.process(frame,0)
        self.assertFalse(s.depth_lost)
        self.assertEqual(sample.knee_x,120)
        self.assertEqual(sample.knee_y,130)

    def test_large_false_match_is_rejected(self):
        t=PointTracker(motion_limit=12);t.select(image(),100,80)
        with patch.object(t,'_flow',return_value=Match(150,130,.95)):
            self.assertIsNone(t.update(image()))
        self.assertEqual(t.point,(100,80))
        self.assertEqual(t.misses,1)

    def test_depth_recovers_without_accepting_rejected_pair(self):
        s=Session();s.depth_enabled=True
        frame=cv2.cvtColor(image(),cv2.COLOR_GRAY2BGR)
        s.select(frame,'bar',100,80)
        # Install textured trackers at distinct positions for deterministic updates.
        for name,point in [('hip',(100,100)),('knee',(100,170))]:
            t=PointTracker(max_search_radius=60);t.select(image(),100,80);t.point=point
            s.trackers[name]=t
        hip,knee=s.trackers['hip'],s.trackers['knee']
        with patch.object(hip,'update',return_value=None), patch.object(knee,'update',return_value=Match(100,170,.9)):
            s.process(frame,0)
        self.assertTrue(s.depth_lost)
        self.assertIn('hip',s.trackers)
        self.assertEqual(hip.point,(100,100))
        with patch.object(hip,'update',return_value=Match(100,101,.9)), patch.object(knee,'update',return_value=Match(100,170,.9)):
            for i in range(3): sample=s.process(frame,(i+1)/30)
        self.assertFalse(s.depth_lost)
        self.assertEqual(sample.depth_state,'above')
        self.assertEqual(s.report()['depth']['state'],'unavailable')

    def test_local_match_survives_ambiguous_wide_search(self):
        t=PointTracker();t.select(image(),100,80)
        with patch.object(t,'_flow',return_value=None), patch.object(t,'_search',side_effect=[Match(100,80,.8),None]) as search:
            self.assertIsNotNone(t.update(image()))
            self.assertEqual(search.call_count,1)

    def test_recovers_after_more_than_five_missing_frames(self):
        s=Session();s.select(cv2.cvtColor(image(),cv2.COLOR_GRAY2BGR),'bar',100,80)
        for i in range(10):
            sample=s.process(cv2.cvtColor(image(hidden=True),cv2.COLOR_GRAY2BGR),i/30)
            self.assertIsNone(sample.bar_x)
        self.assertTrue(s.bar_lost)
        sample=s.process(cv2.cvtColor(image(110,95),cv2.COLOR_GRAY2BGR),11/30)
        self.assertFalse(s.bar_lost)
        self.assertAlmostEqual(sample.bar_x,110,delta=2)
        self.assertEqual(s.report()['missing_frames'],10)

    def test_incomplete_tracking_does_not_judge_rep_completion(self):
        samples=[Sample(i/30,100,50+i*4) for i in range(20)]+[Sample(1,None,None,tracking_gap=True)]
        report=summarize(samples)
        self.assertIsNone(report['sideways_spread_percent'])
        self.assertNotIn('partial rep',' '.join(report['feedback']))
        self.assertIn('unavailable',' '.join(report['feedback']))
