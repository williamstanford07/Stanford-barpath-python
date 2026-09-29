# BarPath update

Replace tracking.py, session.py, rendering.py and phone.html in the existing
GitHub repository with the files in this ZIP. Commit, wait for Render's deploy
to finish, then reload the app. No new dependencies or settings are required.

For IMG_1369(1).mp4, the bar test starts at frame 450 (15 seconds), with the
bar marker at approximately x=235, y=350 on the upright 512-by-910 image.
Analyze the next 20 seconds. Coordinates must not be reused after rotation
or for another clip. The new bar tracker estimates local rigid plate motion.

Depth uses a FIXED horizontal knee-height reference and a tracked hip marker.
Enable Fixed-line depth counter, set the line at the upper knee, and mark the
visible hip crease. Three stable frames above arm the counter; three stable
frames below increment it once. Returning above resets it for another crossing.
A 3-pixel band limits jitter. Missing hip tracking disarms counting until the
hip is reliably above again. The video continues through tracking gaps.

This cannot guarantee depth for hidden hips. The line does not follow knee
height or camera movement, and crossings are not official depth judgments or
necessarily completed repetitions. Review the marker throughout the video.
Only the bar tracking was visually verified on this original clip; the new
fixed-line counting behavior is covered by automated tests, not a claim that
hip tracking succeeds throughout this clip.
