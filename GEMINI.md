# Project: Light Map

This project aims to provide tools for calibrating a projector-camera system.

## Components:

*   **`src/light_map/`**: The core python package containing the modular logic.
    *   **`camera.py`**: Contains the `Camera` class, handling efficient image capture and abstracting differences between Raspberry Pi (GStreamer) and standard webcams (OpenCV).
    *   **`calibration.py`**: Functions for processing chessboard images and calculating camera intrinsics.
    *   **`projector.py`**: Functions for generating calibration patterns and computing the camera-to-projector homography.
    *   **`gestures.py`**: Functions for heuristic-based hand gesture recognition (e.g., Open Palm, Closed Fist, Pointing).
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
