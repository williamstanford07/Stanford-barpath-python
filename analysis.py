"""Descriptive bar-path feedback and assisted 2D depth comparison."""
from dataclasses import dataclass, asdict
import math
import numpy as np


@dataclass
class Sample:
    time_s: float
    bar_x: float | None
    bar_y: float | None
    hip_x: float | None = None
    hip_y: float | None = None
    knee_x: float | None = None
    knee_y: float | None = None
    depth_state: str = "unavailable"
    depth_delta_px: float | None = None
    tracking_gap: bool = False

    def to_dict(self):
        return asdict(self)


def depth_estimate(hip, knee, uncertainty=8):
    """Positive image-y difference means the hip marker is below the knee."""
    if hip is None or knee is None:
        return "unavailable", None
    delta = float(hip[1]-knee[1])
    if not math.isfinite(delta):
        return "unavailable", None
    state = "below" if delta > uncertainty else "above" if delta < -uncertainty else "borderline"
    return state, delta


def summarize(samples):
    points = [s for s in samples if s.bar_x is not None and s.bar_y is not None]
    result = {"tracked_frames": len(points), "missing_frames": len(samples)-len(points),
              "vertical_range_px": None, "maximum_drift_px": None, "sideways_spread_percent": None,
              "feedback": [], "depth": {"state": "unavailable", "deepest_stable_delta_px": None}}
    if len(points) < 12:
        result["feedback"] = ["Track a full descent and ascent before interpreting the path."]
    else:
        xs = np.array([s.bar_x for s in points])
        ys = np.array([s.bar_y for s in points])
        vertical = float(np.ptp(ys))
        drift = float(np.max(np.abs(xs-xs[0])))
        result.update(vertical_range_px=round(vertical, 1), maximum_drift_px=round(drift, 1))
        if vertical < 25:
            result["feedback"] = ["Not enough vertical movement for meaningful path feedback."]
        else:
            spread = float(np.ptp(xs)/vertical*100)
            result["sideways_spread_percent"] = round(spread, 1)
            bottom = int(np.argmax(ys))
            shift = float(xs[bottom]-xs[0])
            direction = "screen-right" if shift > 0 else "screen-left" if shift < 0 else "horizontally"
            down, up = float(ys[bottom]-ys[0]), float(ys[bottom]-ys[-1])
            returned = down > 25 and up > down*.8 and abs(float(ys[-1]-ys[0])) < vertical*.2
            result["feedback"] = [
                f"Side-to-side spread: {spread:.0f}% of vertical range. Maximum drift: {drift:.0f} image px.",
                f"At the lowest tracked bar position, the bar is {abs(shift):.0f} image px {direction} from its start. Screen direction does not establish forward/backward movement.",
                "A down-and-up movement returned near the starting height." if returned else "A return near the starting height was not established. This may be a partial rep.",
                "Compare clips from the same camera position; this is not a technique score."]
    if result["missing_frames"] or any(s.tracking_gap for s in samples):
        result["feedback"].append("Tracking was interrupted. Gaps are not bar movement; re-track before comparing technique.")
    stable = [s for s in samples if s.depth_state in ("below", "above", "borderline") and s.depth_delta_px is not None]
    if stable:
        deepest = max(stable, key=lambda s: s.depth_delta_px)
        result["depth"] = {"state": deepest.depth_state, "deepest_stable_delta_px": round(deepest.depth_delta_px, 1)}
    result["limitations"] = "User-selected markers; image pixels, not physical distance. Depth is an approximate 2D comparison, not a meet ruling or full-body form assessment."
    return result
