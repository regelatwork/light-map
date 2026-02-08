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
  - **`calibration_logic.py`**: Contains the reusable projector calibration sequence.
- **`calibrate.py`**: Entry point script. Performs camera calibration using chessboard images in `images/` and saves `camera_calibration.npz`.
- **`projector_calibration.py`**: Entry point script. Displays a pattern, captures it, and computes the perspective transformation matrix.
- **`hand_tracker.py`**: Entry point script. Continuously tracks hands, projecting landmarks and detecting gestures in real-time with a hierarchical menu system.

## Goal:

The ultimate goal of this project is to enable precise mapping between camera and projector spaces, allowing for applications such as augmented reality projections, interactive displays, or projection mapping.

## File Descriptions:

- **`src/light_map/`**: Source code package.
- **`tests/`**: Unit tests for the project (run with `pytest`).
- **`calibrate.py`**: CLI entry point for camera calibration.
- **`projector_calibration.py`**: CLI entry point for projector calibration.
- **`hand_tracker.py`**: CLI entry point for the interactive hand tracking demo.
- **`camera_calibration.npz`**: Stores the camera matrix and distortion coefficients.
- **`requirements.txt`**: Lists the Python dependencies for this project.
- **`README.md`**: Provides instructions on how to use the scripts in this project.
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
