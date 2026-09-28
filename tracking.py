"""Hybrid OpenCV tracking: local optical flow plus wider appearance matching.

Use a textured marker on the bar sleeve/end. A stationary camera and a clear
view still matter; no tracker can reliably see through a spotter or plate.
"""
from dataclasses import dataclass
import cv2
import numpy as np


@dataclass
class Match:
    x: float
    y: float
    score: float
    method: str = "template"


class PointTracker:
    def __init__(self, search_radius=140, patch_radius=16):
        self.search_radius = search_radius
        self.patch_radius = patch_radius
        self.point = None
        self.template = None
        self.anchor = None
        self.previous = None
        self.features = None
        self.misses = 0

    def _patch(self, gray, x, y):
        r = self.patch_radius
        h, w = gray.shape
        if not (r <= x < w-r and r <= y < h-r):
            return None
        return cv2.getRectSubPix(gray, (2*r+1, 2*r+1), (float(x), float(y)))

    def _features(self, gray):
        mask = np.zeros_like(gray)
        x, y = map(lambda n: int(round(n)), self.point)
        r = self.patch_radius
        mask[max(0, y-r):y+r+1, max(0, x-r):x+r+1] = 255
        return cv2.goodFeaturesToTrack(gray, maxCorners=24, qualityLevel=.02,
                                      minDistance=3, mask=mask, blockSize=3)

    def select(self, gray, x, y):
        patch = self._patch(gray, x, y)
        if patch is None:
            raise ValueError("Choose a point farther from the video edge.")
        if float(patch.std()) < 7:
            raise ValueError("Choose a textured point on the sleeve/end, or add a contrasting tape marker.")
        self.template, self.anchor = patch.copy(), patch.copy()
        self.point, self.previous = (float(x), float(y)), gray.copy()
        self.features = self._features(gray)
        self.misses = 0

    @staticmethod
    def similarity(patch, template):
        if patch is None or float(patch.std()) < 3:
            return -1.0
        return float(cv2.matchTemplate(patch, template, cv2.TM_CCOEFF_NORMED)[0, 0])

    def _flow(self, gray):
        if self.features is None or len(self.features) < 3 or self.previous is None:
            return None
        options = dict(winSize=(25, 25), maxLevel=3,
                       criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, .01))
        nxt, valid, _ = cv2.calcOpticalFlowPyrLK(self.previous, gray, self.features, None, **options)
        if nxt is None:
            return None
        back, back_valid, _ = cv2.calcOpticalFlowPyrLK(gray, self.previous, nxt, None, **options)
        if back is None:
            return None
        original = self.features.reshape(-1, 2)
        forward = nxt.reshape(-1, 2)
        error = np.linalg.norm(back.reshape(-1, 2)-original, axis=1)
        good = (valid.ravel() == 1) & (back_valid.ravel() == 1) & (error < 1.5)
        if np.count_nonzero(good) < 3:
            return None
        displacement = forward[good]-original[good]
        median = np.median(displacement, axis=0)
        consistent = np.linalg.norm(displacement-median, axis=1) < 3
        if np.count_nonzero(consistent) < max(3, int(len(displacement)*.6)):
            return None
        dx, dy = np.median(displacement[consistent], axis=0)
        if max(abs(dx), abs(dy)) > self.search_radius:
            return None
        x, y = self.point[0]+float(dx), self.point[1]+float(dy)
        patch = self._patch(gray, x, y)
        score = self.similarity(patch, self.template)
        anchor_score = self.similarity(patch, self.anchor)
        if score < .70 or anchor_score < .45:
            return None
        return Match(x, y, score, "optical_flow")

    def _search(self, gray, radius):
        r = self.patch_radius
        x, y = map(lambda n: int(round(n)), self.point)
        h, w = gray.shape
        left, top = max(0, x-radius-r), max(0, y-radius-r)
        right, bottom = min(w, x+radius+r+1), min(h, y+radius+r+1)
        region = gray[top:bottom, left:right]
        if min(region.shape) < 2*r+1:
            return None
        scores = cv2.matchTemplate(region, self.template, cv2.TM_CCOEFF_NORMED)
        scores = np.nan_to_num(scores, nan=-1.0, posinf=-1.0, neginf=-1.0)
        _, best, _, location = cv2.minMaxLoc(scores)
        bx, by = location
        alternatives = scores.copy()
        alternatives[max(0, by-r):by+r+1, max(0, bx-r):bx+r+1] = -1
        if best < .72 or best-float(alternatives.max()) < .035:
            return None
        px, py = float(left+bx+r), float(top+by+r)
        if self.similarity(self._patch(gray, px, py), self.anchor) < .50:
            return None
        return Match(px, py, float(best))

    def update(self, gray):
        if self.template is None:
            return None
        match = self._flow(gray)
        if match is None:
            match = self._search(gray, min(28, self.search_radius))
            if match is None or match.score < .88 or self.misses:
                match = self._search(gray, min(400, self.search_radius+self.misses*24))
        if match is None:
            self.misses += 1
            return None
        self.point = (match.x, match.y)
        patch = self._patch(gray, match.x, match.y)
        # Update slowly only on strong matches; preserve the original anchor to limit drift.
        if match.score >= .88 and self.similarity(patch, self.anchor) >= .65:
            self.template = cv2.addWeighted(self.template, .9, patch, .1, 0)
        self.previous = gray.copy()
        self.features = self._features(gray)
        self.misses = 0
        return match
