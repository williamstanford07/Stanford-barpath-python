"""Draw the same branded frame for the viewer and exported video."""
import cv2

RED = (80, 70, 255)  # OpenCV uses BGR, not RGB.
WHITE = (235, 235, 240)


def annotate(frame, session, show_zone=True):
    out = frame.copy()
    h, w = out.shape[:2]
    previous = None
    for sample in session.samples:
        if sample.bar_x is None:
            previous = None
            continue
        point = (round(sample.bar_x), round(sample.bar_y))
        if previous is not None and not sample.tracking_gap:
            cv2.line(out, previous, point, RED, 2, cv2.LINE_AA)
        previous = point
    good = [s for s in session.samples if s.bar_x is not None]
    if good:
        x0 = round(good[0].bar_x)
        for y in range(0, h, 18):
            cv2.line(out, (x0, y), (x0, min(h-1, y+8)), (150, 150, 150), 1)
    for name, tracker in session.trackers.items():
        if tracker.point is None or tracker.misses:
            continue
        x, y = map(round, tracker.point)
        if name == "knee":
            cv2.line(out, (0, y), (w-1, y), WHITE, 2)
            cv2.putText(out, "FIXED KNEE LINE", (12, max(70,y-8)), cv2.FONT_HERSHEY_SIMPLEX, .4, WHITE, 1)
            continue
        color = RED if name == "bar" else WHITE
        if name == "bar" and show_zone:
            r = session.search_radius
            cv2.rectangle(out, (max(0, x-r), max(0, y-r)), (min(w-1, x+r), min(h-1, y+r)), (80, 70, 130), 1)
        cv2.circle(out, (x, y), 10, color, 2, cv2.LINE_AA)
        cv2.putText(out, name.upper(), (max(0, min(w-65, x+14)), max(16, y-12)), cv2.FONT_HERSHEY_SIMPLEX, .45, color, 1, cv2.LINE_AA)
        if name == "knee":
            cv2.line(out, (0, y), (w-1, y), WHITE, 1)
    cv2.rectangle(out, (0, 0), (w, 57), (14, 14, 17), -1)
    cv2.putText(out, "BarPath", (15, 28), cv2.FONT_HERSHEY_SIMPLEX, .9, RED, 2, cv2.LINE_AA)
    cv2.putText(out, "SQUAT REVIEW / WILLIAM STANFORD", (15, 47), cv2.FONT_HERSHEY_SIMPLEX, .38, WHITE, 1, cv2.LINE_AA)
    if session.samples and session.samples[-1].bar_x is None:
        cv2.putText(out, "BAR NOT VISIBLE / SEARCHING", (15, 78), cv2.FONT_HERSHEY_SIMPLEX, .5, RED, 1, cv2.LINE_AA)
    if session.depth_enabled:
        label = "DEPTH UNAVAILABLE / SEARCHING" if session.depth_lost else "DEPTH: WAITING FOR STABLE MARKERS"
        if session.depth_streak >= 3 and not session.depth_lost:
            label = {"above": "HIP ABOVE FIXED LINE", "below": "DEPTH REACHED / BELOW LINE", "borderline": "HIP NEAR LINE"}[session.depth_state]
        cv2.rectangle(out, (0, h-33), (w, h), (14, 14, 17), -1)
        cv2.putText(out, label+f" | COUNT {session.depth_crossings}", (12, h-12), cv2.FONT_HERSHEY_SIMPLEX, .4, WHITE, 1, cv2.LINE_AA)
    return out
