# Hierarchical Menu System

The `hand_tracker.py` application features a hierarchical, gesture-controlled menu system for hands-free operation.

## Menu Interaction

- **Summon Menu**: Perform the **Victory** (Peace sign) gesture and hold it for 1.0 second. The menu will appear at the cursor position.
- **Navigate & Hover**: Move your **index fingertip** to hover over different menu items. Items highlight when hovered.
- **Select Item**: With an item hovered, perform the **Closed Fist** gesture and hold it for 0.8 seconds (Priming). The item will highlight in green.
  - If the item has a sub-menu, you will navigate into it.
  - If the item is an action, it will trigger. Most actions automatically close the menu upon completion.
- **Navigate Back**: Select the **< Back** item (if available) to return to the previous menu level.
- **Dismiss Menu**: Select **Main Menu > < Close** at the top of the root menu to close it manually.
- **Sticky Selection**: To prevent accidental clicks, the cursor "locks" onto an item briefly when you begin a selection gesture.

## Menu Reference

### Main Menu

The root menu providing access to all system functions.

- **< Close**: Closes the menu and enters **Viewing Mode**.
- **Maps**: Opens the [Map Management](#maps-menu) sub-menu.
- **Map Controls**: Closes the menu and enters **Map Mode** (enables Pan/Zoom gestures).
- **Map Settings**: Opens the [Map Settings](#map-settings-menu) sub-menu.
- **Calibration**: Opens the [System Calibration](#calibration-menu) sub-menu.
- **Session**: Opens the [Session Management](#session-menu) sub-menu.
- **Options**: Opens the [System Options](#options-menu) sub-menu.
- **Quit**: Exits the application (`Main Menu > Quit`).

### Maps Menu

Dynamic list of all discovered maps (`maps/*.svg`, `maps/*.png`).

- **(!) <Map Name>**: Indicates the map's grid scale has not been calibrated.
- **(\*) <Map Name>**: Indicates a saved session is available for this map.
- **<Map Name> (Sub-menu)**:
  - **Load Map**: Loads the map and resets the view (`Main Menu > Maps > [Map] > Load Map`).
  - **Load Session**: Loads the map and restores the last saved token positions (`Main Menu > Maps > [Map] > Load Session`).
  - **Calibrate Scale**: Enters **Map Grid Calibration** mode for this specific map (`Main Menu > Maps > [Map] > Calibrate Scale`).
  - **Forget Map**: Removes the map from the registry (`Main Menu > Maps > [Map] > Forget Map`).
- **Scan for Maps**: Manually triggers a scan of the `maps/` directory for new files (`Main Menu > Maps > Scan for Maps`).

### Map Settings Menu

Controls for the currently active map.

- **Rotate CW / CCW**: Rotates the map view by 90 degrees (`Main Menu > Map Settings > Rotate CW`).
- **Reset View**: Restores the default 1:1 scale and centers the map (`Main Menu > Map Settings > Reset View`).
- **Zoom 1:1**: Resets only the zoom level to 1:1 (`Main Menu > Map Settings > Zoom 1:1`).
- **Set Scale**: Enters **Map Grid Calibration** mode to align the digital map with the physical 1-inch tabletop grid (`Main Menu > Map Settings > Set Scale`).
- **Calibrate PPI**: Triggers the **Physical PPI Calibration** wizard (`Main Menu > Map Settings > Calibrate PPI`).

### Calibration Menu

Core system calibration steps. These should be performed in order.

1. **1. Camera Intrinsics**: Calibrates lens distortion using a chessboard target (`Main Menu > Calibration > 1. Camera Intrinsics`).
1. **2. Projector Homography**: Maps camera pixels to projector pixels using a projected pattern (`Main Menu > Calibration > 2. Projector Homography`).
1. **3. Physical PPI**: Calibrates the physical size of projector pixels using a printed ArUco target (`Main Menu > Calibration > 3. Physical PPI`).
1. **4. Camera Extrinsics**: Calibrates the camera's 3D pose to correct for parallax error when tracking tall tokens (`Main Menu > Calibration > 4. Camera Extrinsics`).

### Session Menu

Tools for tracking physical tokens and saving game state.

- **Scan & Save**: Performs a vision scan (Flash, Structured Light, or ArUco) and saves token positions to a session file (`Main Menu > Session > Scan & Save`).
- **Calibrate Flash**: Calibrates the adaptive flash intensity for non-ArUco token detection (`Main Menu > Session > Calibrate Flash`).
- **Load Last Session**: Restores the most recent session for the currently loaded map (`Main Menu > Session > Load Last Session`).
- **Algorithm: [Name]**: Toggles between available detection algorithms: `FLASH`, `STRUCTURED_LIGHT`, and `ARUCO` (`Main Menu > Session > Algorithm: ...`).

### Options Menu

Global system settings and debugging.

- **Toggle Debug**: Shows/hides the vision processing HUD and FPS counter (`Main Menu > Options > Toggle Debug`).
- **Masking (Sub-menu)**:
  - **Projection Masking: ON/OFF**: Toggles dynamic dimming of the projection around hands to improve tracking reliability (`Main Menu > Options > Masking > Projection Masking`).
  - **GM Position (Sub-menu)**: Defines where the Game Master is sitting (e.g., `North`, `South`) to optimize masking and UI placement (`Main Menu > Options > Masking > GM Position > [Direction]`).

## Configuration

Menu interaction timings and styling are defined in `src/light_map/menu_config.py`. The dynamic structure is built in `src/light_map/menu_builder.py`.
