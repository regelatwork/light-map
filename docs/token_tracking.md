# Token Tracking and Session Persistence

The system can detect physical tokens (e.g., minis, dice) placed on the table, map them to the digital grid, and save/restore the session state.

## Scanning a Session

1. Place your physical tokens on the map.
1. Select **"Session > Scan & Save"** from the main menu.
1. The projector will flash **Full White** for a moment (to illuminate tokens and remove map interference).
1. The system captures the scene, detects tokens (handling adjacent tokens via splitting logic), and saves the session.
1. Session files are stored in the `sessions/` directory, uniquely linked to the specific map file.
1. Feedback "Saved X Tokens" will appear.

## Loading a Session

Sessions are linked to specific maps. You can load a session directly from the **"Maps"** sub-menu after selecting a map that has a session available (indicated by `(*)`).

Alternatively, select **"Session > Load Last Session"** to restore the state from `session.json`.

1. The map will load the saved viewport (pan/zoom/rotation).
1. **"Ghost Tokens"** (cyan circles) will be projected at the saved locations, allowing you to restore the physical setup.

## Adaptive Flash Calibration

To improve token detection in different ambient lighting conditions, you can calibrate the intensity of the flash.

1. Select **"Session > Calibrate Flash"** from the main menu.
1. The projector will display a bright white screen and begin ramping the intensity down.
1. The system will analyze the camera feed for saturation at each step.
1. Once it finds the brightest, non-saturating level, it will automatically save it.
1. A confirmation message will show the optimal intensity level found. This value will be used for all subsequent token scans.
