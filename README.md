# STANFORD BarPath 🏋️

A Python-based squat video analysis prototype that combines my interest in fitness with my Information Systems studies at Texas State.

## Features
- Tracks a manually selected point on the barbell
- Visualizes the bar’s movement path
- Estimates squat depth using manually selected hip and knee markers
- Exports an annotated video and tracking measurements
- Supports video uploads through a phone or computer browser

## Built With
Python, OpenCV, Flask, HTML, and Render.

## Development
I used YouTube tutorials and AI tools to help learn concepts, generate and revise code, and troubleshoot issues. I tested the app with real lifting videos to identify problems and guide improvements.

The app is deployed on Render. Access currently requires a password.

## Current Limitations
Tracking can lose the selected point because of lighting, camera movement, or objects blocking the bar. The video continues processing, but untracked frames remain gaps.

Depth estimates depend on marker placement and camera angle. This is a learning project, not a replacement for a coach or competition judge.

## Next Steps
- Improve tracking reliability
- Reduce video processing time
- Improve depth estimates and usability

