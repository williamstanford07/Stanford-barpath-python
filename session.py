"""Shared state: video processing, marker validity, and measurement history."""
import math
import cv2
from tracking import PointTracker
from analysis import Sample, depth_estimate, summarize


class Session:
    def __init__(self, search_radius=300):
        self.search_radius = search_radius
        self.depth_enabled = False
        self.trackers = {}
        self.samples = []
        self.depth_lost = False
        self.depth_had_gaps = False
        self.depth_state = "unavailable"
        self.depth_delta = None
        self.depth_streak = 0
        self.uncertainty = 8
        self.bar_lost = False
        self.interrupted = False

    def clear(self):
        enabled = self.depth_enabled
        self.__init__(self.search_radius)
        self.depth_enabled = enabled

    def point(self, name):
        tracker = self.trackers.get(name)
        return tracker.point if tracker else None

    def select(self, frame, name, x, y):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        tracker = PointTracker(self.search_radius if name == "bar" else 60,
                               max_search_radius=None if name == "bar" else 60,
                               motion_limit=12 if name == "bar" else None)
        tracker.select(gray, x, y)
        other = self.point("knee" if name == "hip" else "hip") if name != "bar" else None
        if other and math.dist(tracker.point, other) < 30:
            raise ValueError("Hip and knee markers must be distinct points on the same visible leg.")
        self.trackers[name] = tracker
        # Reselecting begins a new measurement segment.
        self.samples.clear()
        self.bar_lost = self.interrupted = False
        self.depth_state, self.depth_delta, self.depth_streak = "unavailable", None, 0
        self.depth_lost = False
        self.depth_had_gaps = False
        if self.point("hip") and self.point("knee"):
            self.uncertainty = max(8, math.dist(self.point("hip"), self.point("knee"))*.07)

    def ready(self):
        return "bar" in self.trackers and (not self.depth_enabled or all(n in self.trackers for n in ("hip", "knee")))

    def process(self, frame, time_s):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        bar_tracker = self.trackers["bar"]
        bar_tracker.search_radius = self.search_radius
        bar = bar_tracker.update(gray)
        self.bar_lost = bar is None and bar_tracker.misses >= 5
        if bar is None:
            self.interrupted = True
        hip = knee = None
        if self.depth_enabled and "hip" in self.trackers and "knee" in self.trackers:
            old_hip, old_knee = self.point("hip"), self.point("knee")
            snapshots = {n: self.trackers[n].__dict__.copy() for n in ('hip', 'knee')}
            hp, kp = self.trackers["hip"].update(gray), self.trackers["knee"].update(gray)
            max_step = min(60, max(30, math.dist(old_hip, old_knee)*.35)
                           + max(snapshots[n]['misses'] for n in snapshots)*5)
            if (hp is None or kp is None or math.dist((hp.x, hp.y), (kp.x, kp.y)) < 30
                    or math.dist(old_hip, (hp.x, hp.y)) > max_step or math.dist(old_knee, (kp.x, kp.y)) > max_step):
                self.depth_lost = True
                self.depth_had_gaps = True
                self.depth_state, self.depth_delta, self.depth_streak = "unavailable", None, 0
                # Preserve the last trusted pair. A rejected match must not
                # become the template/position used to recover on later frames.
                for name, snapshot in snapshots.items():
                    self.trackers[name].__dict__.update(snapshot)
                    self.trackers[name].misses = snapshot['misses']+1
            else:
                self.depth_lost = False
                hip, knee = (hp.x, hp.y), (kp.x, kp.y)
                state, delta = depth_estimate(hip, knee, self.uncertainty)
                self.depth_streak = self.depth_streak+1 if state == self.depth_state else 1
                self.depth_state, self.depth_delta = state, delta
        sample = Sample(time_s, bar.x if bar else None, bar.y if bar else None,
                        hip[0] if hip else None, hip[1] if hip else None,
                        knee[0] if knee else None, knee[1] if knee else None,
                        self.depth_state if self.depth_streak >= 3 else "unavailable",
                        self.depth_delta if self.depth_streak >= 3 else None, bar is None)
        self.samples.append(sample)
        return sample

    def report(self):
        report = summarize(self.samples)
        report["depth"]["tracking_lost"] = self.depth_had_gaps
        report["depth"]["ended_lost"] = self.depth_lost
        report["depth"]["observed_state"] = report['depth']['state']
        if self.depth_had_gaps:
            report["depth"]["state"] = "unavailable"
            report["depth"]["deepest_stable_delta_px"] = None
        return report
