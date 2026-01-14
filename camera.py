import cv2
import numpy as np
import time
import os
import subprocess

def is_raspberry_pi():
    """Check if the script is running on a Raspberry Pi."""
    try:
        with open("/sys/firmware/devicetree/base/model", "r") as f:
            return "raspberry pi" in f.read().lower()
    except Exception:
        return False

def get_gstreamer_pipeline(
    camera_name="/base/axi/pcie@1000120000/rp1/i2c@88000/imx708@1a",
    target_width=1920,
    target_height=1080,
    framerate=30
):
    """
    Returns a GStreamer pipeline string for capturing from a specific Raspberry Pi camera.
    This pipeline uses libcamerasrc with a specific camera name and handles debayering and format conversion.
    """
    # This pipeline uses libcamerasrc with a specific camera name and directly requests RGBx format.
    pipeline = (
        f"libcamerasrc camera-name={camera_name} ! "
        f"video/x-raw, format=BGR, width=2304, height=1296, framerate={framerate}/1 ! "
        f"videoconvert ! "
        f"videoscale ! "
        f"video/x-raw, width={target_width}, height={target_height}, format=BGR ! "
        f"appsink drop=1"
    )
    return pipeline

def capture_image():
    """
    Captures an image from the camera.
    
    This function checks if the script is running on a Raspberry Pi and uses the
    appropriate camera library (GStreamer or OpenCV) to capture an image.
    Returns:
        numpy.ndarray: The captured image frame.
    """
    cap = None
    if is_raspberry_pi():
        print("Raspberry Pi detected. Using GStreamer with specific camera path and RGBx format.")
        pipeline = get_gstreamer_pipeline()
        print(f"Pipeline string: {pipeline}")
        build_info = cv2.getBuildInformation()
        print(f"cv2 Build info: {build_info}")
        cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
        
    else:
        print("Not a Raspberry Pi. Attempting to open camera with OpenCV...")
        cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        raise Exception("Cannot open camera. Please check connection and configuration.")
        
    ret, frame = cap.read()
    cap.release()
        
    if not ret:
        raise Exception("Failed to capture image from camera")

    print("Image captured successfully.")
    return frame
