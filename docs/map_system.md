# SVG Map System

The system can load and project SVG map files (e.g., floor plans). Map settings like pan, zoom, and rotation are automatically persisted in `map_state.json`.

## Loading Maps

To start the application and register one or more maps, use the `--maps` argument with files or globs:

```bash
python -m light_map --maps "maps/*.svg" "maps/*.png"
```

You can also use the legacy `--map` argument to load a specific map immediately:

```bash
python -m light_map --map path/to/your/map.svg
```

## Map Selection

A dynamic "Maps" menu is available in the main menu:

- **(!) Map Name**: Indicates the map's grid scale has not been calibrated.
- **(\*) Map Name**: Indicates a saved session is available for this map.
- **Action Menu**: Selecting a map opens a sub-menu (**Main Menu > Maps > [Map Name]**) to:
  - **Load Map**: Load the map and reset tokens.
  - **Load Session**: Load the map and restore saved token positions.
  - **Calibrate Scale**: Enter manual scale alignment mode.
  - **Forget Map**: Remove the map from the registry.

## Map Interaction

Switch to **Map Mode** by selecting **Main Menu > Map Interaction Mode**.
Note: When a map is loaded (or the menu is closed), the app defaults to **Viewing Mode** (read-only) to prevent accidental shifts.

- **Pan**: Use the **Closed Fist** gesture and move your hand to drag the map.
- **Zoom**: Use the **Two-Hand Pointing** gesture (index fingers extended on both hands). Move hands apart to zoom in, and closer to zoom out.
- **Rotate**: Use the **Rotate CW/CCW** options in the **Main Menu > Map Settings** sub-menu.
- **Reset**: Use **Reset View** to restore 1:1 scale and center view, or **Zoom 1:1** to reset zoom only.
- **Exit Map Mode**: Perform the **Victory** gesture to return to the main menu.

## Viewing Mode

When a map is loaded, or when the menu is closed, the system enters **Viewing Mode**.
In this mode:

- The map is fully opaque (1.0).
- Pan/Zoom gestures are **disabled** to ensure stability during gameplay.
- **Toggle Tokens**: Use the **Shaka** gesture to show/hide ghost tokens.
- **Exclusive Vision**: Perform the **Pointing** gesture and dwell on a token for 2 seconds to see its Line-of-Sight. (See [Exclusive Vision Mode](exclusive_vision.md)).
- **Summon Menu**: Use the **Victory** gesture to open the menu.

## Scale Calibration (Manual Alignment)

If the map's grid size is unknown or the map is an image, you can manually calibrate the scale.

1. Select **Main Menu > Map Settings > Set Scale** (or **Maps > [Map Name] > Calibrate Scale**).
1. The map will reset to a base view, and a **1-inch grid** will be projected.
1. Use Pan/Zoom gestures to align the map's grid lines with the projected crosshairs.
1. Perform the **Victory** gesture to confirm. The system saves this scale and restores your previous view.

## Scale Calibration (PPI)

To achieve 1:1 mapping (1 inch on map = 1 inch in real life), you must calibrate the **Projector Pixels Per Inch (PPI)**.

1. **Generate Target**: Run `python scripts/generate_calibration_target.py` to create `calibration_target.svg`.
1. **Print**: Print the target at 100% scale. It contains two **ArUco markers (ID 0 and 1)** exactly 100mm apart.
1. **Calibrate**: Select **Main Menu > Calibration > 3. Physical PPI** (or **Map Settings > Calibrate PPI**).
1. **Detect**: Place the printed target on the surface. The system will detect the markers and calculate the PPI.
1. **Verify & Confirm**: A 1-inch grid will be projected. Verify its accuracy and perform the **Victory** gesture to save the calibration.
