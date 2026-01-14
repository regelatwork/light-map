# Projector-Camera Calibration

This project provides tools for calibrating a camera and a projector-camera system, and for real-time hand tracking projection.

## Camera Calibration

The `calibrate.py` script calibrates a camera using a series of chessboard images.

### Usage

1.  Ensure you have `pyenv` installed and Python 3.12 (e.g., `3.12.9`) is available through `pyenv`. You can set your local Python version using:
    ```bash
    pyenv local 3.12.9
    ```

2.  Create the virtual environment with system site packages (necessary for `picamera2` on Raspberry Pi):

    ```bash
    python -m venv --system-site-packages .venv
    ```

3.  Activate the virtual environment and install the dependencies:

    ```bash
    source .venv/bin/activate
    pip install -r requirements.txt
    ```
3.  Place your chessboard calibration images in the `images/` directory.

4.  Run the script:

    ```bash
    python calibrate.py
    ```

5.  The script will save the camera matrix and distortion coefficients to `camera_calibration.npz`.

## Projector-Camera Calibration

The `projector_calibration.py` script calculates the perspective transformation matrix to map camera coordinates to screen (projector) coordinates.

### Raspberry Pi Setup
If you are running this script on a Raspberry Pi, you will need to install GStreamer and the `libcamera` plugin. You can do this by running the following command:
```bash
sudo apt update && sudo apt install -y gstreamer1.0-tools gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-libcamera
```

### Usage

1.  First, ensure you have calibrated your camera and have the `camera_calibration.npz` file.
2.  Run the script:

    ```bash
    python projector_calibration.py
    ```
3.  The script will display a fullscreen chessboard pattern. Your camera needs to be able to see this pattern.
3.  The script will then capture an image, find the chessboard, and print the resulting transformation matrix to the console.

## Hand Tracking and Projection

The `hand_tracker.py` script continuously gets images from the camera, detects up to two hands, and projects the positions of the detected hand landmarks onto a fullscreen projector window.

### Usage

1.  First, ensure you have calibrated your camera and projector as described in the sections above, and have the `camera_calibration.npz` file.
2.  Run the script:

    ```bash
    python hand_tracker.py
    ```
3.  The script will display a fullscreen black window on the projector. As hands are detected by the camera, their landmarks will be projected onto this screen.
4.  Press 'q' to quit the application.

