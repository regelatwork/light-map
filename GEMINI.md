# Project: Light Map

This project aims to provide tools for calibrating a projector-camera system.

## Components:

*   **`src/light_map/`**: The core python package containing the modular logic.
    *   **`camera.py`**: Contains the `Camera` class, handling efficient image capture and abstracting differences between Raspberry Pi (GStreamer) and standard webcams (OpenCV).
    *   **`calibration.py`**: Functions for processing chessboard images and calculating camera intrinsics.
    *   **`projector.py`**: Functions for generating calibration patterns and computing the camera-to-projector homography.
    *   **`gestures.py`**: Functions for heuristic-based hand gesture recognition (e.g., Open Palm, Closed Fist, Pointing, Gun, Victory).
    *   **`common_types.py`**: Shared type definitions for the menu system.
    *   **`menu_config.py`**: Configuration for the hierarchical menu system.
    *   **`input_manager.py`**: Handles input smoothing and sticky hand logic.
    *   **`menu_system.py`**: Core logic for the hierarchical menu system.
    *   **`renderer.py`**: Renders the menu UI.
*   **`calibrate.py`**: Entry point script. Performs camera calibration using chessboard images in `images/` and saves `camera_calibration.npz`.
*   **`projector_calibration.py`**: Entry point script. Displays a pattern, captures it, and computes the perspective transformation matrix.
*   **`hand_tracker.py`**: Entry point script. Calibrates the projector and then continuously tracks hands, projecting landmarks and detecting gestures in real-time.

## Goal:

The ultimate goal of this project is to enable precise mapping between camera and projector spaces, allowing for applications such as augmented reality projections, interactive displays, or projection mapping.

## File Descriptions:

*   **`src/light_map/`**: Source code package.
*   **`tests/`**: Unit tests for the project (run with `pytest`).
*   **`calibrate.py`**: CLI entry point for camera calibration.
*   **`projector_calibration.py`**: CLI entry point for projector calibration.
*   **`hand_tracker.py`**: CLI entry point for the interactive hand tracking demo.
*   **`camera_calibration.npz`**: Stores the camera matrix and distortion coefficients.
*   **`requirements.txt`**: Lists the Python dependencies for this project.
*   **`README.md`**: Provides instructions on how to use the scripts in this project.
*   **`GEMINI.md`**: This file, providing a high-level overview of the project.
*   **`images/`**: A directory containing the chessboard images used for camera calibration.
*   **`.venv/`**: The Python virtual environment.

## Feature Tracking: Hierarchical Menus (feat/hierarchical-menus)

*   [x] **Phase 0: Shared Types & Configuration**
    *   Created `src/light_map/common_types.py`
    *   Created `src/light_map/menu_config.py`
*   [x] **Phase 0.5: Persistence Infrastructure**
    *   Updated `projector_calibration.py` to save resolution.
    *   Updated `hand_tracker.py` to load calibration safely with fallbacks.
*   [x] **Phase 0.8: Input Abstraction**
    *   Created `src/light_map/input_manager.py`
    *   Added unit tests `tests/test_input_manager.py`
*   [x] **Phase 1: Core Logic**
*   [x] **Phase 2: Renderer**
*   [x] **Phase 3: Integration**
    *   Refactored `hand_tracker.py` into `InteractiveApp` for testability.
    *   Implemented Debug Mode (`--debug`).
    *   Verified with unit tests.