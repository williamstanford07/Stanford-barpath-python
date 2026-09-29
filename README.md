# STANFORD BarPath

A squat video tracker by William Stanford, built with Python, OpenCV, Flask and HTML.

Upload a clip, select the bar end and watch its path through the lift. Optional depth tracking follows a selected hip marker against a fixed knee-height line. Results include an annotated MP4, a path image, measurements and a report.

## Use the app

1. Upload a short side-view video.
2. Choose a frame just before the descent and rotate the image upright if needed.
3. Mark the center of the visible bar end.
4. For depth, enable **Fixed-line depth counter**, set the line at the upper knee and mark the hip crease.
5. Choose the clip length and select **Analyze lift**. Save the MP4 when it is ready.

The default search radius is 300 pixels. Use the slider to select the starting frame. Changing the frame or rotation clears the markers.

## Tracking

The bar tracker uses optical flow and a local rigid-motion estimate, with template matching for recovery. Depth counts a stable crossing from above the fixed line to below it; the hip must return above before another count. Missing hip tracking interrupts counting.

The knee line stays in the same place on screen. It does not follow knee movement. These are image measurements, not a competition depth ruling or a full-body form assessment. Obstruction, clothing, camera movement and similar-looking objects can affect tracking. Review the markers in the output.

## Run locally

Use Python 3.12:

```sh
pip install -r requirements.txt
python mobile.py
```

Open the private local link printed in the terminal. Your phone can use that link on the same Wi-Fi. Keep the terminal running. Local mode is intended for your own network.

## Hosted app

The included Dockerfile runs `python cloud.py`. The existing Render service uses this entry point.

Set `BARPATH_PASSWORD` (at least 24 characters) and `SESSION_SECRET` (at least 32 characters) as environment variables. Keep these outside the repository. Hosted login requires HTTPS. The service reads `PORT`, defaulting to 10000; its health endpoint is `/healthz`.

Run one process and one instance. This is a single-owner app: anyone with the password shares access to the temporary clips. It accepts up to 250 MB per upload, five stored clips and one analysis at a time, with up to 60 seconds per analysis. Restarting or redeploying clears temporary results.

See START_HERE.txt to update an existing deployment.

## Checks

```sh
python -m unittest discover -s tests
```

The tests cover tracking recovery, fixed-line counting, rotation, authentication, uploads and video exports.
