# Projector-Camera Calibration

This project provides tools for calibrating a camera and a projector-camera system.

## Camera Calibration

The `calibrate.py` script calibrates a camera using a series of chessboard images.

### Usage

1.  Activate the virtual environment and install the dependencies:
    ```bash
    source venv/bin/activate
    pip install -r requirements.txt
    ```
2.  Place your chessboard calibration images in the `images/` directory.
3.  Run the script:
    ```bash
    python calibrate.py
    ```
4.  The script will save the camera matrix and distortion coefficients to `camera_calibration.npz`.

## Projector-Camera Calibration

The `projector_calibration.py` script calculates the perspective transformation matrix to map camera coordinates to screen (projector) coordinates.

### Raspberry Pi Setup
If you are running this script on a Raspberry Pi, you will need to install the `libcamera` system dependency. You can do this by running the following command:
```bash
sudo apt update && sudo apt install -y python3-libcamera
```

### Usage

1.  First, ensure you have calibrated your camera and have the `camera_calibration.npz` file.
2.  Run the script:
    ```bash
    python projector_calibration.py
    ```
3.  The script will display a fullscreen chessboard pattern. Your camera needs to be able to see this pattern.
4.  The script will then capture an image, find the chessboard, and print the resulting transformation matrix to the console.