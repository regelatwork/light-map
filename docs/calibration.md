# Calibration Guide

This guide covers the calibration steps for the camera and projector-camera system.

## Camera Calibration

The `calibrate.py` script calibrates a camera using a series of chessboard images.

### Usage

1. Ensure you have `pyenv` installed and Python 3.12 (e.g., `3.12.9`) is available through `pyenv`. You can set your local Python version using:

   ```bash
   pyenv local 3.12.9
   ```

1. Create the virtual environment with system site packages (necessary for `picamera2` on Raspberry Pi):

   ```bash
   python -m venv --system-site-packages .venv
   ```

1. Activate the virtual environment and install the dependencies:

   ```bash
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

1. Place your chessboard calibration images in the `images/` directory.

1. Run the script:

   ```bash
   python calibrate.py
   ```

1. The script will save the camera matrix and distortion coefficients to `camera_calibration.npz`.

## Projector-Camera Calibration

The `projector_calibration.py` script calculates the perspective transformation matrix to map camera coordinates to screen (projector) coordinates. It also captures raw calibration points to enable **non-linear distortion correction** (barrel/keystone compensation).

### Raspberry Pi Setup

If you are running this script on a Raspberry Pi, you will need to install GStreamer and the `libcamera` plugin. You can do this by running the following command:

```bash
sudo apt update && sudo apt install -y gstreamer1.0-tools gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-libcamera
```

### Usage

1. First, ensure you have calibrated your camera and have the `camera_calibration.npz` file.

1. Run the script:

   ```bash
   python projector_calibration.py
   ```

1. The script will display a fullscreen chessboard pattern. Your camera needs to be able to see this pattern.

1. The script will then capture an image, find the chessboard, and print the resulting transformation matrix to the console. It saves both the matrix and the raw point correspondences to `projector_calibration.npz`.

## Distortion Visualization

After projector calibration, you can visualize the mapping residuals (non-linear errors) using the `visualize_distortion.py` tool.

### Usage

1. Ensure you have run `projector_calibration.py`.

1. Run the visualization script:

   ```bash
   python visualize_distortion.py
   ```

1. The script will generate a vector plot (`distortion_field.png`) showing the magnitude and direction of the distortion across the screen. This is useful for diagnosing calibration quality and lens distortion.
