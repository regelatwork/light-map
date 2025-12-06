# Camera Calibration with OpenCV

This project contains a Python script to calibrate a camera using a series of checkerboard images.

## Setup

1.  **Clone the repository or download the files.**

2.  **Create a Python virtual environment:**
    ```bash
    python3 -m venv venv
    ```

3.  **Activate the virtual environment:**
    ```bash
    source venv/bin/activate
    ```

4.  **Install the required dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Usage

1.  **Place your calibration images in the `images` directory.**
    The images should be in `.jpg` format and contain a clear view of a checkerboard pattern.

2.  **Run the calibration script:**
    ```bash
    python3 calibrate.py
    ```

3.  **Follow the on-screen instructions.**
    The script will process each image one by one. An image window will pop up showing the detected checkerboard corners. Press any key to advance to the next image.

## Output

After processing all the images, the script will:

*   Print the **Camera Matrix** and **Distortion Coefficients** to the console.
*   Save the calibration data to a file named `camera_calibration.npz`. This file contains the camera matrix and distortion coefficients, which you can load in other applications for correcting image distortion.
