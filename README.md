# STANFORD BarPath — hosted Python edition

Python/OpenCV squat tracking, assisted depth markers, descriptive feedback, and MP4 exports, with a red-and-black mobile browser interface.

Prepared for a single-owner Render web service. This package has not yet been deployed. Connect a Render account and provide the source through a Git repository before deployment. The included render.yaml describes a free-plan service; verify plan availability and resource limits during deployment. No paid plan is authorized by this package.

## Runtime

Build with the Dockerfile. Run one instance and one Python process: `python cloud.py`. PORT defaults to 10000. Set BARPATH_PASSWORD (at least 24 characters) and SESSION_SECRET (at least 32 characters) as host secrets. The blueprint generates both. Never commit secrets. The host must provide HTTPS; cookies require it. /healthz is the public health endpoint.

Open the assigned HTTPS address and enter BARPATH_PASSWORD, retrieved privately from your host's environment settings. Do not paste it into chat. Upload a short recorded clip, choose the start frame, select the bar end, optionally mark hip crease and knee top, then analyze. Your laptop does not need to stay on.

## Data and limits

This is a private single-owner app, not a multi-user service. Anyone with the password shares access to the temporary clips. Clips are processed on the server; maximum upload 250 MB, five stored clips, one analysis at a time, at most 60 seconds per analysis. Delete uploaded clips and results removes all clips. Download desired results first. Restarting or redeploying clears temporary files; no durable storage is configured. Resource-limited hosting may require shorter clips. No live phone camera streaming.

Depth compares manually selected hip/knee image points and cannot infer hidden anatomy. A spotter, rotating plate, camera angle, or obstruction may cause inaccurate tracking; inspect the output. Feedback is descriptive, not a safety or competition judgment.

## Validation

Synthetic tracker tests, authentication, video upload, Python analysis, MP4 conversion, downloads and clearing are tested locally. Hosting and physical phone use remain unverified until deployment.
