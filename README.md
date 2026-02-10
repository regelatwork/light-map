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

The `hand_tracker.py` script continuously gets images from the camera, detects up to two hands, and projects the positions of the detected hand landmarks onto a fullscreen projector window. It also displays:

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

## Vision Enhancement (Interference Mitigation)

To improve hand tracking reliability when projecting bright images, the system includes a real-time vision enhancement pipeline (Gamma Correction + CLAHE).

### Live Tuning

You can adjust the vision parameters while the application is running to find the optimal settings for your lighting conditions. The settings are automatically saved to `map_state.json`.

- **`[` / `]`**: Decrease / Increase Gamma (Darkens/Brightens highlights).
- **`{` / `}`**: Decrease / Increase CLAHE Clip Limit (Adjusts local contrast).

### Debug Mode

To see exactly what the AI sees (the enhanced camera frame), run with the `--view-enhanced` flag:

```bash
python hand_tracker.py --view-enhanced
```

This opens a secondary window showing the pre-processed video feed with the current Gamma and CLAHE values overlaid.

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

The system can load and project SVG map files (e.g., floor plans). Map settings like pan, zoom, and rotation are automatically persisted in `map_state.json`.

### Loading a Map

To start the application with a map, use the `--map` argument:

```bash
python hand_tracker.py --map path/to/your/map.svg
```

### Map Interaction

Switch to **Map Mode** by selecting "Map Controls" from the main menu.

- **Pan**: Use the **Open Palm** gesture and move your hand to drag the map.
- **Zoom**: Use the **Two-Hand Pointing** gesture (index fingers extended on both hands). Move hands apart to zoom in, and closer to zoom out. A 1-inch grid will appear to assist with scaling.
- **Rotate**: Use the "Rotate CW/CCW" options in the "Map Settings" sub-menu.
- **Reset**: Use the "Reset View" option in the "Map Settings" sub-menu.
- **Exit Map Mode**: Perform the **Victory** gesture to return to the main menu.

## Scale Calibration (PPI)

To achieve 1:1 mapping (1 inch on map = 1 inch in real life), you must calibrate the **Projector Pixels Per Inch (PPI)**.

1. **Generate Target**: Run `python generate_calibration_target.py` to create `calibration_target.svg`.
1. **Print**: Print the target at 100% scale. It contains two **ArUco markers (ID 0 and 1)** exactly 100mm apart.
1. **Calibrate**: Select "Map Settings" -> "Calibrate Scale" from the menu.
1. **Detect**: Place the printed target on the surface. The system will detect the markers and calculate the PPI.
1. **Verify & Confirm**: A 1-inch grid will be projected. Verify its accuracy and perform the **Victory** gesture to save the calibration.

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
