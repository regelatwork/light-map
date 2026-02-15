# Project: Light Map

This project aims to provide tools for calibrating a projector-camera system.

## Components:

- **`src/light_map/`**: The core python package containing the modular logic.
  - **`camera.py`**: Contains the `Camera` class, handling efficient image capture and abstracting differences between Raspberry Pi (GStreamer) and standard webcams (OpenCV).
  - **`calibration.py`**: Functions for processing chessboard images and calculating camera intrinsics.
  - **`projector.py`**: Functions for generating calibration patterns and computing the camera-to-projector homography.
  - **`gestures.py`**: Functions for heuristic-based hand gesture recognition (e.g., Open Palm, Closed Fist, Pointing, Gun, Victory).
  - **`common_types.py`**: Shared type definitions for the menu system.
  - **`menu_config.py`**: Configuration for the hierarchical menu system.
  - **`input_manager.py`**: Handles input smoothing and sticky hand logic.
  - **`menu_system.py`**: Core logic for the hierarchical menu system.
  - **`renderer.py`**: Renders the menu UI.
  - **`interactive_app.py`**: Orchestrates the interaction between camera, hand tracking, and menu system.
  - **`calibration_logic.py`**: Contains the reusable projector calibration sequence and PPI detection.
  - **`svg_loader.py`**: Loads and renders SVG files using `svgelements`.
  - **`map_system.py`**: Manages map viewport state (pan, zoom, rotation).
  - **`map_config.py`**: Handles persistence for map settings and global calibration data.
  - **`camera_pipeline.py`**: Manages a separate thread for camera capture and AI processing to decouple FPS from rendering.
  - **`token_tracker.py`**: Computer vision pipeline for detecting physical tokens (minis, dice) using adaptive thresholding and watershed segmentation.
  - **`session_manager.py`**: Handles JSON serialization for saving and restoring map state and token positions.
- **`calibrate.py`**: Entry point script. Performs camera calibration using chessboard images in `images/` and saves `camera_calibration.npz`.
- **`projector_calibration.py`**: Entry point script. Displays a pattern, captures it, and computes the perspective transformation matrix.
- **`hand_tracker.py`**: Entry point script. Continuously tracks hands, projecting landmarks and detecting gestures in real-time with a hierarchical menu system and SVG map support. Supports live vision tuning.
- **`generate_calibration_target.py`**: Standalone script to generate a printable calibration target for PPI scale calibration.

## Goal:

The ultimate goal of this project is to enable precise mapping between camera and projector spaces, allowing for applications such as augmented reality projections, interactive displays, or projection mapping.

## File Descriptions:

- **`src/light_map/`**: Source code package.
- **`tests/`**: Unit tests for the project (run with `pytest`).
- **`calibrate.py`**: CLI entry point for camera calibration.
- **`projector_calibration.py`**: CLI entry point for projector calibration.
- **`hand_tracker.py`**: CLI entry point for the interactive hand tracking demo.
- **`camera_calibration.npz`**: Stores the camera matrix and distortion coefficients.
- **`map_state.json`**: Stores persistent application state, including map viewports, PPI calibration, and vision enhancement parameters.
- **`session.json`**: Stores the last saved session state (map file, viewport, token positions).
- **`requirements.txt`**: Lists the Python dependencies for this project.
- **`README.md`**: Provides instructions on how to use the scripts in this project.
- **`tests/README.md`**: Documentation for the unit testing suite, including coverage and running instructions.
- **`GEMINI.md`**: This file, providing a high-level overview of the project.
- **`images/`**: A directory containing the chessboard images used for camera calibration.
- **`.venv/`**: The Python virtual environment.

## Development Guidelines

### Coding Standards

- **Python Style & Linting**: Use [Ruff](https://beta.ruff.rs/docs/). Run `ruff format .` and `ruff check . --fix`.
- **Markdown Formatting**: Use [mdformat](https://github.com/executablebooks/mdformat). Run `mdformat .`.

### Testing

- **Framework**: Use [pytest](https://docs.pytest.org/).
- **Source Layout**: The project uses a `src` layout. Configure `pytest` via `pytest.ini` (already present) to include `src` in the `pythonpath`.
- **Naming**: Test files should be prefixed with `test_` and located in the `tests/` directory.

## Feature Tracking: Hierarchical Menus (feat/hierarchical-menus)

- [x] **Phase 0: Shared Types & Configuration**
- [x] **Phase 0.5: Persistence Infrastructure**
- [x] **Phase 0.8: Input Abstraction**
- [x] **Phase 1: Core Logic**
- [x] **Phase 2: Renderer**
- [x] **Phase 3: Integration (InteractiveApp)**
- [x] **Phase 4: Calibration Integration**
  - Extracted calibration logic to `src/light_map/calibration_logic.py`.
  - Implemented dynamic configuration reloading in `InteractiveApp`.
  - Enabled in-app calibration via "Calibrate" menu item.

## Feature Tracking: SVG Map Support (feat/svg-map-support)

- [x] **Phase 1: SVG Loading & Rendering**
  - Implemented `SVGLoader` using `svgelements`.
- [x] **Phase 2: Viewport & State Management**
  - Implemented `MapSystem` for Pan, Pinned Zoom, and 90-degree Rotation.
- [x] **Phase 3: Integration & Rendering**
  - Updated `Renderer` for layered background support.
  - Integrated map layer into `InteractiveApp`.
- [x] **Phase 4: Interaction & Gestures**
  - Implemented "Map Mode" with panning and two-hand zoom.
  - Implemented "Viewing Mode" (default state) with read-only map view.
- [x] **Phase 5: Calibration & Persistence**
  - Implemented JSON persistence via `map_state.json`.
  - Added scale (PPI) calibration flow.

## Feature Tracking: Projection Interference Mitigation

- [ ] **Phase 1: Vision Enhancer Pipeline**
  - *Status: Reverted (Feb 2026). Gamma/CLAHE proved ineffective and degraded tracking.*
- [ ] **Phase 2: Channel Selection & Color Isolation**
  - *Status: Reverted (Feb 2026). Single channel processing did not improve robustness.*
- [ ] **Phase 3: Static Background Subtraction (Manual)**
  - *Status: Reverted (Feb 2026). Removed background but did not correct hand texture/color corruption.*
- [x] **Phase 4: UI-Based Interference Mitigation**
  - **Menu Isolation**: Hide map (opacity 0.0) when `MenuSystem` is active.
  - **Interactive Dimming**: Dim map (opacity 0.5) when in `Map Mode` (Pan/Zoom).
  - Implemented in `Renderer.render` and `InteractiveApp`.
- [x] **Phase 5: Sticky Selection & Minimalist UI**
  - **Sticky Selection**: Last hovered menu item remains selected until a new item is hovered. Prevents accidental deselection during hand closing.
  - **Perimeter Highlight**: Replaced filled buttons with thick, high-contrast borders to minimize light projection on the hand.

## Feature Tracking: Performance Optimization

- [x] **Phase 1: Dynamic Resolution Rendering**
  - Implemented caching and quality scaling in `SVGLoader`.
  - Updated `InteractiveApp` to use lower resolution (0.25x) during map interactions (Pan/Zoom).
  - Uses `lru_cache` and quantized parameters to maximize cache hits.
- [x] **Phase 2: Pipeline Parallelism**
  - Created `CameraPipeline` to run Camera Capture -> Vision Enhancement -> MediaPipe in a separate thread.
  - Decoupled UI rendering loop from Camera/AI processing latency.
  - Implemented thread-safe data transfer using `VisionData` dataclass.

## Feature Tracking: Map Grid Scaling (feat/map-grid-scaling)

- [x] **Phase 1: Logic & Data Structures**
  - `MapConfig` persistence for `grid_spacing_svg` and `scale_factor_1to1`.
  - `SVGLoader` vector-based grid auto-detection.
- [x] **Phase 2: Manual Calibration**
  - "Set Scale" menu item (Manual Alignment Mode).
  - Dimmed map background and green crosshair overlays (1 inch reference).
  - "Calibration View" isolation: Resets view to base scale/orientation during calibration.
- [x] **Phase 3: Interaction Refinement**
  - **Fixed Pivot Zoom**: Zoom interactions scale around screen center.
  - **Rotation Fix**: Coordinate transforms correctly handle map rotation.
  - **Zoom 1:1**: Menu item to reset user zoom to calibrated base scale.
- [x] **Phase 4: Robustness**
  - **Raster Fallback**: Auto-detection uses autocorrelation for image-based maps.
  - **Warning UI**: "GRID UNCALIBRATED" warning when scale is unknown.

## Feature Tracking: Token Tracking & Persistence

- [x] **Phase 1: Computer Vision Pipeline**
  - Implemented `TokenTracker` using adaptive thresholding, morphological ops, and watershed segmentation.
  - Added heuristic splitting logic for adjacent tokens (vertical/horizontal pairs) based on aspect ratio.
- [x] **Phase 2: Persistence Infrastructure**
  - Implemented `SessionManager` to save/load `session.json`.
  - Stores Map Viewport + Token Positions (World & Grid coordinates).
- [x] **Phase 3: Application Integration**
  - Added `SCANNING` mode to `InteractiveApp`.
  - Implemented "Flash Scan" sequence: White Flash -> Wait 500ms (Sync) -> Capture -> Detect -> Save.
  - Added "Session" menu with "Scan & Save" and "Load Session".
  - Renders "Ghost Tokens" (cyan overlays) for saved sessions.
- [x] **Phase 4: Adaptive Flash Calibration**
  - Added "Calibrate Flash" menu item.
  - Implemented automated calibration sequence that ramps down flash intensity.
  - Uses saturation detection (`is_saturated`) to find the optimal non-saturating brightness level.
  - Saves the calibrated `flash_intensity` to `map_state.json`.

## Feature Tracking: Map Loading & Session Management (feat/map-loading-sessions)

- [x] **Phase 1: CLI & Discovery**
  - Implemented `--maps` argument with glob support.
  - Added automatic map discovery and pruning in `MapConfigManager`.
- [x] **Phase 2: Session Persistence**
  - Refactored `SessionManager` to link sessions to map files via path hashing.
  - Session files now stored in `sessions/` directory with unique names.
- [x] **Phase 3: Dynamic Menu UI**
  - Implemented `MenuBuilder` for dynamic injection of "Maps" submenu.
  - Added visual status indicators (`(!)`, `(*)`) for calibration and sessions.
  - Added "Map Action" sub-menus for Load, Load Session, Calibrate, and Forget.
- [x] **Phase 4: Integration**
  - Updated `InteractiveApp` to support parameter passing via `action_id` (pipe-delimited).
  - Integrated "Scan for Maps" with live menu refreshing.
