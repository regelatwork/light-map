# Project: Light Map

This project aims to provide tools for calibrating a projector-camera system.

## Components:

*   **`calibrate.py`**: A Python script that performs camera calibration using a set of chessboard images. It generates a `camera_calibration.npz` file containing the camera matrix and distortion coefficients.
*   **`camera.py`**: A utility script for capturing images from a camera, with support for both Raspberry Pi (using `picamera2`) and general systems (using OpenCV).
*   **`project-calibration.py`**: A Python script that, given a camera calibration file, displays a fullscreen calibration pattern, captures an image from the camera, and calculates the perspective transformation matrix to map camera coordinates to screen (projector) coordinates. This matrix is essential for accurately projecting content onto surfaces.

## Goal:

The ultimate goal of this project is to enable precise mapping between camera and projector spaces, allowing for applications such as augmented reality projections, interactive displays, or projection mapping.

## File Descriptions:

*   **`calibrate.py`**: Performs camera calibration using chessboard images.
*   **`camera.py`**: Provides utilities for capturing images from a camera.
*   **`projector_calibration.py`**: Calculates the transformation matrix between camera and projector coordinates.
*   **`camera_calibration.npz`**: Stores the camera matrix and distortion coefficients obtained from `calibrate.py`.
*   **`requirements.txt`**: Lists the Python dependencies for this project.
*   **`README.md`**: Provides instructions on how to use the scripts in this project.
*   **`GEMINI.md`**: This file, providing a high-level overview of the project.
*   **`images/`**: A directory containing the chessboard images used for camera calibration.
*   **`venv/`**: A directory for the Python virtual environment.