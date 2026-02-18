# Project: Light Map

Light Map is an interactive Augmented Reality (AR) tabletop platform that merges physical gaming with digital enhancements. By precisely calibrating a projector-camera pair, the system enables hand-gesture interaction, dynamic map projection, and real-time physical token tracking.

## Components:

- **`src/light_map/`**: The core python package containing the modular logic.
  - **`camera.py`**: Handles efficient image capture, abstracting Raspberry Pi (GStreamer) and standard webcams (OpenCV).
  - **`calibration.py`**: Camera intrinsic calibration using chessboard targets.
  - **`projector.py`**: Homography computation and non-linear distortion correction (`ProjectorDistortionModel`).
  - **`gestures.py`**: Heuristic-based hand gesture recognition (Open Palm, Closed Fist, Pointing, etc.).
  - **`menu_system.py`**: Core logic for hierarchical, gesture-controlled menus.
  - **`renderer.py`**: High-performance UI and map rendering.
  - **`interactive_app.py`**: Orchestrates vision pipelines, gestures, and the digital tabletop experience.
  - **`map_system.py`**: Manages digital map viewports (pan, zoom, rotation).
  - **`token_tracker.py`**: Computer vision pipeline for tracking physical minis and dice using Structured Light and Flash-based detection.
  - **`camera_pipeline.py`**: Decouples vision processing (MediaPipe) from the rendering loop for high FPS.
  - **`session_manager.py`**: Handles persistence for tabletop sessions (maps, tokens, viewports).
- **`calibrate.py`**: Entry point for camera calibration.
- **`projector_calibration.py`**: Entry point for projector-camera registration.
- **`hand_tracker.py`**: The main interactive application entry point.

## Goal:

The goal of Light Map is to create a seamless bridge between physical and digital tabletop gaming. By turning any flat surface into an interactive display that "understands" the physical objects and hands placed upon it, the system provides a low-cost, high-immersion alternative to traditional digital tabletops.

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
- **`visualize_distortion.py`**: Script to visualize projector distortion residuals.
- **`projector_calibration.npz`**: Stores projector homography matrix and raw calibration points.

## Development Guidelines

### Coding Standards

- **Python Style & Linting**: Use [Ruff](https://beta.ruff.rs/docs/). Run `ruff format .` and `ruff check . --fix`.
- **Markdown Formatting**: Use [mdformat](https://github.com/executablebooks/mdformat). Run `mdformat .`.

### Testing

- **Framework**: Use [pytest](https://docs.pytest.org/).
- **Source Layout**: The project uses a `src` layout. Configure `pytest` via `pytest.ini` (already present) to include `src` in the `pythonpath`.
- **Naming**: Test files should be prefixed with `test_` and located in the `tests/` directory.

## Feature Tracking

### Completed Features

- **Hierarchical Menus**: Gesture-controlled menu system for hands-free control, featuring "Sticky Selection" and a minimalist UI to minimize light interference. (Design: \[hierarchical_menus.md\](file:///home/rchandia/light_map/features/hierarchical_menus.md))
- **SVG Map Support**: Vector-based map rendering with pan, zoom, 90° rotation, and dark-theme auto-inversion. (Design: \[svg_map_support.md\](file:///home/rchandia/light_map/features/svg_map_support.md))
- **Performance Optimization**: Parallel processing pipeline and dynamic resolution rendering to maintain high FPS. (Design: \[performance_optimization.md\](file:///home/rchandia/light_map/features/performance_optimization.md))
- **Map Grid Scaling**: Auto-detection and manual calibration to align digital maps with physical 1-inch grids. (Design: \[map_grid_scaling.md\](file:///home/rchandia/light_map/features/map_grid_scaling.md))
- **Map Loading & Session Management**: Dynamic map discovery, persistent session saving for token positions, and map-specific metadata. (Design: \[map_loading_sessions.md\](file:///home/rchandia/light_map/features/map_loading_sessions.md))
- **Projector Distortion Correction**: Non-linear residual correction to compensate for lens distortion (barrel/keystone) at projection edges. (Design: \[projector_distortion_correction.md\](file:///home/rchandia/light_map/features/projector_distortion_correction.md))
- **Token Tracking (Flash-based)**: CV pipeline using adaptive thresholding and watershed segmentation to detect physical minis and dice. (Design: \[token_tracking_brainstorm.md\](file:///home/rchandia/light_map/features/token_tracking_brainstorm.md))
- **Projection Interference Mitigation**: UI-driven strategy (menu isolation, interactive dimming) to preserve hand tracking reliability. (Design: \[projection_interference_mitigation.md\](file:///home/rchandia/light_map/features/projection_interference_mitigation.md))

### Active / Proposed Features

- **Structured Light Token Detection**: Utilizing dot grid disparity to detect tokens regardless of color or contrast. (Design: \[structured_light_token_detection.md\](file:///home/rchandia/light_map/features/structured_light_token_detection.md))
- **Refactor InteractiveApp (Scene Architecture)**: Transitioning to a scene-based architecture for improved maintainability and testability. (Design: \[refactor_interactive_app.md\](file:///home/rchandia/light_map/features/refactor_interactive_app.md))
