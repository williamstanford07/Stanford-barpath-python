"""Shared state: video processing, marker validity, and measurement history."""
import math
from types import SimpleNamespace
import cv2
from tracking import PointTracker, RigidBarTracker
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
        self.minimum_depth_separation = 8
        self.bar_lost = False
        self.interrupted = False
        self.depth_crossings = 0
        self.depth_armed = False

    def clear(self):
        enabled = self.depth_enabled
        self.__init__(self.search_radius)
        self.depth_enabled = enabled

    def point(self, name):
        tracker = self.trackers.get(name)
        return tracker.point if tracker else None

    def select(self, frame, name, x, y):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        tracker_class = RigidBarTracker if name == "bar" else PointTracker
        tracker = tracker_class(self.search_radius if name == "bar" else 60,
                               max_search_radius=None if name == "bar" else 60,
                               motion_limit=12 if name == "bar" else None)
        if name == "knee":
            h, w = gray.shape
            if not (math.isfinite(x) and math.isfinite(y) and 0 <= x < w and 0 <= y < h):
                raise ValueError("Place the knee line inside the image.")
            tracker = SimpleNamespace(point=(float(x), float(y)), misses=0)
        else:
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
        self.depth_crossings = 0
        self.depth_armed = False
        if self.point("hip") and self.point("knee"):
            self.uncertainty = 3
            self.minimum_depth_separation = max(8, min(20,
                math.dist(self.point('hip'), self.point('knee'))*.1))

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
            snapshots = {n: self.trackers[n].__dict__.copy() for n in ('hip',)}
            hp = self.trackers["hip"].update(gray)
            max_step = min(60, max(30, math.dist(old_hip, old_knee)*.35)
                           + max(snapshots[n]['misses'] for n in snapshots)*5)
            if hp is None or math.dist(old_hip, (hp.x, hp.y)) > max_step:
                self.depth_lost = True
                self.depth_had_gaps = True
                self.depth_state, self.depth_delta, self.depth_streak = "unavailable", None, 0
                self.depth_armed = False
                # Preserve the last trusted pair. A rejected match must not
                # become the template/position used to recover on later frames.
                for name, snapshot in snapshots.items():
                    self.trackers[name].__dict__.update(snapshot)
                    self.trackers[name].misses = snapshot['misses']+1
            else:
                self.depth_lost = False
                # The knee selection is a fixed screen-height reference, not
                # a tracked anatomical landmark. Never update its position.
                hip, knee = (hp.x, hp.y), old_knee
                state, delta = depth_estimate(hip, knee, self.uncertainty)
                self.depth_streak = self.depth_streak+1 if state == self.depth_state else 1
                self.depth_state, self.depth_delta = state, delta
                if self.depth_streak >= 3:
                    if state == "above":
                        self.depth_armed = True
                    elif state == "below" and self.depth_armed:
                        self.depth_crossings += 1
                        self.depth_armed = False
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
        report["depth"]["mode"] = "fixed_knee_line"
        report["depth"]["confirmed_crossings"] = self.depth_crossings
        report["depth"]["reference_y"] = self.point("knee")[1] if self.point("knee") else None
        if self.depth_had_gaps:
            report["depth"]["state"] = "unavailable"
            report["depth"]["deepest_stable_delta_px"] = None
        return report
