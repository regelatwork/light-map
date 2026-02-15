# Projector-Camera Calibration

This project provides tools for calibrating a camera and a projector-camera system, and for real-time hand tracking projection.

## Camera Calibration

The `calibrate.py` script calibrates a camera using a series of chessboard images.

### Usage

1. Ensure you have `pyenv` installed and Python 3.12 (e.g., `3.12.9`) is available through `pyenv`. You can set your local Python version using:

   ```bash
   pyenv local 3.12.9
   ```

1. Create the virtual environment with system site packages (necessary for `picamera2` on Raspberry Pi):

   ```bash
   python -m venv --system-site-packages .venv
   ```

1. Activate the virtual environment and install the dependencies:

   ```bash
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

1. Place your chessboard calibration images in the `images/` directory.

1. Run the script:

   ```bash
   python calibrate.py
   ```

1. The script will save the camera matrix and distortion coefficients to `camera_calibration.npz`.

## Projector-Camera Calibration

The `projector_calibration.py` script calculates the perspective transformation matrix to map camera coordinates to screen (projector) coordinates.

### Raspberry Pi Setup

If you are running this script on a Raspberry Pi, you will need to install GStreamer and the `libcamera` plugin. You can do this by running the following command:

```bash
sudo apt update && sudo apt install -y gstreamer1.0-tools gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-libcamera
```

### Usage

1. First, ensure you have calibrated your camera and have the `camera_calibration.npz` file.

1. Run the script:

   ```bash
   python projector_calibration.py
   ```

1. The script will display a fullscreen chessboard pattern. Your camera needs to be able to see this pattern.

1. The script will then capture an image, find the chessboard, and print the resulting transformation matrix to the console.

## Hand Tracking and Projection

The `hand_tracker.py` script continuously gets images from the camera, detects up to two hands, and projects the positions of the detected hand landmarks onto a fullscreen projector window. It utilizes a **multi-threaded pipeline** to decouple camera processing from UI rendering, ensuring smooth interaction even during heavy computation. It also displays:

- Real-time FPS (Frames Per Second).
- The number of detected hands.
- The recognized gesture for each hand (labeled Left/Right).

### Supported Gestures

The system currently recognizes the following gestures:

- **Open Palm**: All fingers extended.
- **Closed Fist**: All fingers curled.
- **Pointing**: Index finger extended.
- **Gun**: Thumb and Index fingers extended.
- **Victory**: Index and Middle fingers extended.
- **Shaka**: Thumb and Pinky extended.
- **Rock**: Index and Pinky extended.

### Usage

1. First, ensure you have calibrated your camera and projector as described in the sections above, and have the `camera_calibration.npz` file.

1. Run the script:

   ```bash
   python hand_tracker.py
   ```

1. The script will display a fullscreen black window on the projector. As hands are detected by the camera, their landmarks will be projected onto this screen.

1. Press 'q' to quit the application.

## Hierarchical Menu System

The `hand_tracker.py` script also features a hierarchical menu system, allowing for interactive control using hand gestures.

### Menu Interaction

- **Summon Menu**: Perform the **Victory** (Peace sign) gesture and hold it for a short duration (`SUMMON_TIME` defined in `menu_config.py`). The menu will appear on the projector screen.
- **Navigate & Hover**: Once the menu is active, move your **index fingertip** to hover over different menu items.
- **Select Item**: With an item hovered, perform the **Closed Fist** gesture and hold it for a short duration (`PRIMING_TIME` defined in `menu_config.py`). This will select the item.
  - If the item has sub-menus, you will navigate into the sub-menu.
  - If the item is an action, the action will be triggered, and if `should_close_on_trigger` is true for that item, the menu will close.
- **Calibrate**: Select "Settings" -> "Calibrate" to trigger the projector calibration sequence without leaving the application. The new calibration will be automatically saved and reloaded.
- **Navigate Back**: Select the "< Back" item to return to the previous menu level.
- **Dismiss Menu**: Select the "< Close" item at the top of the menu to close it.
- **Quit Application**: Select the "Quit" item at the bottom of the menu to exit the application.

## SVG Map Support

The system can load and project SVG map files (e.g., floor plans). Map settings like pan, zoom, and rotation are automatically persisted in `map_state.json`. To ensure high performance, the system employs **dynamic resolution rendering**, lowering quality during pan/zoom interactions and snapping to full resolution when static.

### Loading Maps

To start the application and register one or more maps, use the `--maps` argument with files or globs:

```bash
python hand_tracker.py --maps "maps/*.svg" "maps/*.png"
```

You can also use the legacy `--map` argument to load a specific map immediately:

```bash
python hand_tracker.py --map path/to/your/map.svg
```

### Map Selection

A dynamic "Maps" menu is available in the main menu:

- **(!) Map Name**: Indicates the map's grid scale has not been calibrated.
- **(\*) Map Name**: Indicates a saved session is available for this map.
- **Action Menu**: Selecting a map opens a sub-menu to:
  - **Load Map**: Load the map and reset tokens.
  - **Load Session**: Load the map and restore saved token positions.
  - **Calibrate Scale**: Enter manual scale alignment mode.
  - **Forget Map**: Remove the map from the registry.

### Map Interaction

Switch to **Map Mode** by selecting "Map Controls" from the main menu.
Note: When a map is loaded (or the menu is closed), the app defaults to **Viewing Mode** (read-only) to prevent accidental shifts.

- **Pan**: Use the **Closed Fist** gesture and move your hand to drag the map.
- **Zoom**: Use the **Two-Hand Pointing** gesture (index fingers extended on both hands). Move hands apart to zoom in, and closer to zoom out.
- **Rotate**: Use the "Rotate CW/CCW" options in the "Map Settings" sub-menu.
- **Reset**: Use "Reset View" to restore 1:1 scale and center view, or "Zoom 1:1" to reset zoom only.
- **Exit Map Mode**: Perform the **Victory** gesture to return to the main menu.

### Viewing Mode

When a map is loaded, or when the menu is closed, the system enters **Viewing Mode**.
In this mode:
- The map is fully opaque (1.0).
- Pan/Zoom gestures are **disabled** to ensure stability during gameplay.
- **Toggle Tokens**: Use the **Shaka** gesture to show/hide ghost tokens.
- **Summon Menu**: Use the **Victory** gesture to open the menu.

### Scale Calibration (Manual Alignment)

If the map's grid size is unknown or the map is an image, you can manually calibrate the scale.

1. Select "Map Settings > Set Scale".
1. The map will reset to a base view, and a **1-inch grid** will be projected.
1. Use Pan/Zoom gestures to align the map's grid lines with the projected crosshairs.
1. Perform the **Victory** gesture to confirm. The system saves this scale and restores your previous view.

## Scale Calibration (PPI)

To achieve 1:1 mapping (1 inch on map = 1 inch in real life), you must calibrate the **Projector Pixels Per Inch (PPI)**.

1. **Generate Target**: Run `python generate_calibration_target.py` to create `calibration_target.svg`.
1. **Print**: Print the target at 100% scale. It contains two **ArUco markers (ID 0 and 1)** exactly 100mm apart.
1. **Calibrate**: Select "Map Settings" -> "Calibrate Scale" from the menu.
1. **Detect**: Place the printed target on the surface. The system will detect the markers and calculate the PPI.
1. **Verify & Confirm**: A 1-inch grid will be projected. Verify its accuracy and perform the **Victory** gesture to save the calibration.

## Token Tracking & Session Persistence

The system can detect physical tokens (e.g., minis, dice) placed on the table, map them to the digital grid, and save/restore the session state.

### Scanning a Session

1. Place your physical tokens on the map.
1. Select **"Session > Scan & Save"** from the main menu.
1. The projector will flash **Full White** for a moment (to illuminate tokens and remove map interference).
1. The system captures the scene, detects tokens (handling adjacent tokens via splitting logic), and saves the session.
1. Session files are stored in the `sessions/` directory, uniquely linked to the specific map file.
1. Feedback "Saved X Tokens" will appear.

### Loading a Session

Sessions are linked to specific maps. You can load a session directly from the **"Maps"** sub-menu after selecting a map that has a session available (indicated by `(*)`).

Alternatively, select **"Session > Load Last Session"** to restore the state from `session.json`.

1. The map will load the saved viewport (pan/zoom/rotation).
1. **"Ghost Tokens"** (cyan circles) will be projected at the saved locations, allowing you to restore the physical setup.

### Debug Mode

To visualize hand tracking, gestures, and system stats (FPS), run the tracker with the debug flag:

```bash
python hand_tracker.py --debug
```

This will display an overlay with:

- FPS counter
- Hand count
- Recognized gesture name
- Cursor position
- Usage instructions

### Configuration

The menu structure and interaction timings are defined in `src/light_map/menu_config.py`.
