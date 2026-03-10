# Configuration Documentation

This document describes the various configuration and state files used in the Light Map project.

## Visual Configuration via Web Dashboard

While most settings can be manually edited in JSON files, the **Light Map Control Dashboard** (available at `http://localhost:8000`) provides a more intuitive way to manage configuration.

### 1. Map Browser
Instead of manually updating `last_used_map`, you can browse and load maps from the **Asset Library** in the sidebar.

### 2. Grid Origin Calibration
The **Configuration Sidebar** in the dashboard allows you to manually enter and update the `grid_origin_svg_x` and `grid_origin_svg_y` offsets for the active map with immediate visual feedback.

### 3. Vision and Display
Use the **Vision Control** module to toggle "Exclusive Vision" (projector masking) and "Hand/Token Masking" modes without needing to navigate the in-projection menu system.

### 4. Calibration Wizards
The dashboard's **Calibration Wizards** provide a guided, step-by-step experience for all calibration routines, including a live video feed for better visualization during setup.

---

## Environment & Development

### `.python-version`

Specifies the Python version to be used with tools like `pyenv` or `uv`.

- **Current Version:** `3.12.9`

### `requirements.txt`

Lists the Python dependencies required for the project. These can be installed using `pip install -r requirements.txt`.

### `pytest.ini`

Configures `pytest` for running tests.

- **`pythonpath`**: Includes `src` to allow absolute imports from the `light_map` package.
- **`testpaths`**: Specifies the directory where tests are located (`tests`).

## Vision & Calibration

### `camera_calibration.npz`

Stores the camera's intrinsic parameters, obtained during camera calibration.

- **`mtx`**: The camera matrix (focal lengths and optical center).
- **`dist`**: Lens distortion coefficients.

### `camera_extrinsics.npz`

Stores the camera's extrinsic parameters (pose relative to the tabletop).

- **`rvec`**: Rotation vector.
- **`tvec`**: Translation vector.

### `projector_calibration.npz`

Stores the registration between the camera and the projector.

- **`homography`**: The 3x3 homography matrix.
- **`pts_src`**: Source points in projector space.
- **`pts_dst`**: Corresponding points in camera space.

## Application State

### `map_state.json`

Persistent configuration for the map system and global application settings. Managed by `MapConfigManager` in `src/light_map/map_config.py`.

- **`global`**:
  - `projector_ppi`: Pixels per inch of the projector on the table. (Calibrate via **Main Menu > Calibration > 3. Physical PPI**)
  - `flash_intensity`: Brightness used for token detection. (Calibrate via **Main Menu > Session > Calibrate Flash**)
  - `last_used_map`: Path to the last opened SVG map.
  - `detection_algorithm`: Algorithm used for token tracking. (Toggle via **Main Menu > Session > Algorithm**)
  - `enable_hand_masking`: Toggle for projection masking. (Toggle via **Main Menu > Options > Masking > Projection Masking**)
  - `gm_position`: Direction where the GM is sitting. (Set via **Main Menu > Options > Masking > GM Position**)
- **`maps`**: A dictionary keyed by SVG map paths, storing map-specific data:
  - `viewport`: Last used pan, zoom, and rotation.
  - `grid_spacing_svg`: Physical grid spacing in SVG units.
  - `grid_origin_svg_x/y`: Origin of the coordinate system on the map.
  - `physical_unit_inches`: Physical size of a grid square (usually 1.0).
  - `aruco_overrides`: Map-specific overrides for ArUco marker IDs.

### `tokens.json`

Stores global token definitions, including size profiles and default ArUco marker assignments. Managed by `MapConfigManager`. This file is separate to allow for easier sharing and management of token libraries.

- **`token_profiles`**: Definitions of token sizes (small, medium, large, huge) and their physical heights.
- **`aruco_defaults`**: Global default names and profiles for ArUco marker IDs.

### `light_map.log`

Log output from all Light Map applications (`python -m light_map`, `scripts/calibrate.py`, `scripts/projector_calibration.py`). Stored in the XDG-compliant state directory (usually `~/.local/state/light_map/`). Uses `RotatingFileHandler` with 10MB max size and 5 backups. Entries are attributed to their originating file and line number (e.g., `[__main__.py:123]`).

### `session.json`

Stores the state of the current or last gaming session. Managed by `SessionManager` in `src/light_map/session_manager.py`.

- **`map_file`**: Path to the active map.
- **`viewport`**: Current pan, zoom, and rotation.
- **`tokens`**: List of detected tokens, including their IDs, world coordinates, grid positions, and detection confidence.

## Internal Python Configurations

### `src/light_map/map_config.py`

Contains the `dataclasses` that define the structure of `map_state.json`. It is the source of truth for the available configuration fields.

### `src/light_map/menu_config.py`

Contains constants and configuration for the gesture-controlled menu system:

- **Timing Constants**: Delays for locking, priming, and summoning menus.
- **UI Styling**: Item width, max visible items, font scaling, and padding.
- **Gesture Mappings**: Maps specific `GestureType`s to actions like Select, Summon, Zoom, and Pan.
- **Colors**: BGR color tuples for various menu states (Normal, Hover, Selected, Confirm, etc.).

## Manual Configuration Examples

While some settings are managed via the UI and calibration scripts, others (like ArUco token definitions) are currently best managed by manually editing the configuration files.

### Defining Token Size Profiles (in `tokens.json`)

Profiles define standard physical dimensions for different types of tokens. These are used globally in the `token_profiles` section of `tokens.json`.

```json
"token_profiles": {
  "small": { "size": 1, "height_mm": 15.0 },
  "medium": { "size": 1, "height_mm": 25.0 },
  "large": { "size": 2, "height_mm": 40.0 },
  "huge": { "size": 3, "height_mm": 60.0 }
}
```

### Global ArUco Marker Defaults (in `tokens.json`)

Assign names, types, and profiles to ArUco marker IDs globally. These apply across all maps unless overridden.

```json
"aruco_defaults": {
  "42": {
    "name": "Wizard PC",
    "type": "PC",
    "profile": "small"
  },
  "10": {
    "name": "Dragon Boss",
    "type": "NPC",
    "size": 3,
    "height_mm": 80.0
  }
}
```

### Map-Specific ArUco Overrides

You can override a global marker definition for a specific map (e.g., if a player changes characters or a marker represents a different NPC on a specific map). This is stored within the entry for that map in the `maps` dictionary.

```json
"maps": {
  "/home/user/light_map/maps/dungeon.svg": {
    "aruco_overrides": {
      "42": {
        "name": "Polymorphed Wizard (Sheep)",
        "type": "PC",
        "profile": "small"
      },
      "15": {
        "name": "Huge Golem",
        "type": "NPC",
        "size": 3,
        "height_mm": 75.0
      }
    },
    "...": "..."
  }
}
```
