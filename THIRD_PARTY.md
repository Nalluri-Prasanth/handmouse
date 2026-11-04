# Repository research and attribution

Reviewed and downloaded public repositories on 2026-11-02:

- https://github.com/Eiten810/hand-gesture-controller — revision `5274367d5ccaef0c1ff1763ff22bfaff68ac40e6`. Reviewed its separation of gesture recognition, relative motion, button state, and scrolling. This repository uses the legacy MediaPipe solutions API. No code copied.
- https://github.com/Rcidshacker/airmouse — revision `2c40147a52d749dc7b2226271647e43896ca1468`. Reviewed its Windows input support, gesture states, and adaptive filter. Its many shortcut gestures were not included. No code copied.
- https://github.com/mdelaba/visionpointer — revision `45e93ac05f709ff83efc7d5f9a67144db48da27d`. Apache License 2.0. `smoothing.py` includes its `OneEuroFilter` class extracted unchanged from `src/web_pointer.py`, with only a new module attribution header and NumPy import. The full license is included in `LICENSE-visionpointer.txt`. The browser/voice/MCP features are not part of Hand Mouse Studio.

The camera model is Google's MediaPipe Hand Landmarker (float16, version 1), copied from the model already downloaded for the earlier project: https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task . Model documentation: https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker .

This is a custom Windows redesign informed by the repositories, with a reused licensed smoothing component; it is not an unmodified upstream application.
