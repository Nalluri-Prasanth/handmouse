# Hand Mouse Studio

Hand Mouse Studio controls the Windows pointer using a webcam and one hand. Move with small finger or wrist motions, rest to click, and scroll with short two-finger strokes.

## Quick start

You need Windows, a webcam, and Python 3.13. From PowerShell:

```powershell
git clone https://github.com/Nalluri-Prasanth/handmouse.git
cd handmouse
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\Start-HandMouse.cmd
```

The hand landmark model is included. The app starts paused. Press **F8** or select **Start control** to enable it. Use the practice target to try a click. **F8** pauses from any app, and **F10** exits.

## Recommended controls: Rest to click

| Action | Control |
| --- | --- |
| Move | Point with index finger; move finger/wrist within a small area |
| Click | Point at the target and hold still for 0.9 seconds; the ring fills before clicking |
| Re-arm clicking | Move the pointer at least 38 pixels from the last click |
| Right click | Briefly touch thumb to middle fingertip; separate before another click (works in both click modes) |
| Scroll | Raise index + middle, fold ring + little; short up/down strokes; hold still to stop |
| Reposition | Fold fingers, move your hand comfortably, then point again |
| Double click | Choose **Next rest: double click**, then point and rest at the target |
| Drag | Choose **Next rest: drag / drop**, rest at target, move, then rest again to drop |
| Pause / resume | F8, anywhere, or Start/Pause button |
| Quit | F10, anywhere, or close the window |

Keep your elbow supported. Use the **Practice target** button to check clicking before controlling other apps. In rest mode, holding still triggers a click: pause with F8 when you want to read or leave your hand in view. The click ring passes input through to the target underneath it.

## Optional pinch mode

Select **Pinch**. First separate thumb and index to arm it. Pinch briefly, then separate to complete a standard press/release click. Move your palm while holding the pinch to drag; holding without moving does not automatically become a drag. The pinch tolerance slider adjusts how close the fingertips must come. Two quick press/release pinches use Windows double-click timing.

## Settings

Pointer sensitivity, scroll sensitivity, rest time, pinch tolerance, and click method save automatically in `settings.json`. Changes reset gesture references to avoid cursor jumps. Settings are separate from the older application.

Hand loss, pauses, camera stalls, and shutdown release held buttons. Screen-corner fail-safe remains enabled. Only one hand is tracked. Camera processing runs locally, in a worker thread; no video is uploaded.

## Troubleshooting and testing

- If the camera is unavailable, close other apps using it, check Windows camera permissions, and relaunch.
- If tracking is intermittent, use even lighting and keep your hand in frame.
- If a pinch is missed, adjust **Pinch tolerance** in the control panel.

Run the gesture tests with `.\.venv\Scripts\python.exe -m unittest test_engine -v`. Tests simulate gestures without moving your real pointer or opening the webcam.

The Studio entry point is `app.py`. Gesture logic lives in `engine.py`, with tests in `test_engine.py`. The original prototype remains available in `main.py`.
## GitHub sources

See **THIRD_PARTY.md** for reviewed repositories, source revisions, and the Apache-licensed smoothing component reused in this application. Other gesture and UI code was written for this redesign.

Webcam tracking still depends on lighting, angle, and visibility of your fingers. Automated checks cover control logic; comfortable timing and accuracy need a live trial with your hand.
