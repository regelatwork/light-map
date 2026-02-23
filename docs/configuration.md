# Configuration Documentation

This document describes the various configuration and state files used in the Light Map project.

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
  - `projector_ppi`: Pixels per inch of the projector on the table.
  - `flash_intensity`: Brightness used for token detection.
  - `last_used_map`: Path to the last opened SVG map.
  - `detection_algorithm`: Algorithm used for token tracking (e.g., `FLASH`, `STRUCTURED_LIGHT`).
  - `token_profiles`: Definitions of token sizes (small, medium, large, huge) and their physical heights.
  - `aruco_defaults`: Global default names and profiles for ArUco marker IDs.
  - `enable_hand_masking`: Toggle for hand-tracking-based projection masking.
- **`maps`**: A dictionary keyed by SVG map paths, storing map-specific data:
  - `viewport`: Last used pan, zoom, and rotation.
  - `grid_spacing_svg`: Physical grid spacing in SVG units.
  - `grid_origin_svg_x/y`: Origin of the coordinate system on the map.
  - `physical_unit_inches`: Physical size of a grid square (usually 1.0).
  - `aruco_overrides`: Map-specific overrides for ArUco marker IDs.

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
