STANFORD BarPath
I built this to track the bar in my squat videos and get a better look at how it moves during a rep. I'm an Information Systems student at Texas State, so this was a way to connect what I'm learning with my interest in fitness.
It's built with Python, OpenCV, Flask and HTML, and the hosted version runs on Render.
What it does
- Tracks a barbell point you select in the video
- Draws the bar path as the lift plays
- Tracks a selected hip point against a fixed knee-height line
- Counts stable crossings below that line
- Exports the video, a path image and tracking measurements
