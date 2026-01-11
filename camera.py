import cv2
import numpy as np
import time

def is_raspberry_pi():
    """Check if the script is running on a Raspberry Pi."""
    try:
        with open("/sys/firmware/devicetree/base/model", "r") as f:
            return "raspberry pi" in f.read().lower()
    except Exception:
        return False

def capture_image():
    """
    Captures an image from the camera.
    
    This function checks if the script is running on a Raspberry Pi and uses the
    appropriate camera library (picamera2 or OpenCV) to capture an image.
    
    Returns:
        numpy.ndarray: The captured image frame.
    """
    if is_raspberry_pi():
        from picamera2 import Picamera2
        print("Raspberry Pi detected. Using picamera2.")
        picam2 = Picamera2()
        config = picam2.create_still_configuration(main={"size": (1920, 1080)})
        picam2.configure(config)
        picam2.start()
        time.sleep(2)
        frame = picam2.capture_array()
        picam2.stop()
        # Convert RGBA to BGR for OpenCV
        frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)
        print("Image captured successfully.")
    else:
        print("Attempting to open camera with OpenCV...")
        cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
        if not cap.isOpened():
            print("Failed to open with V4L2 backend, trying default backend.")
            cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            raise Exception("Cannot open camera. Please check connection and configuration.")
        
        print("Camera opened successfully.")
        
        time.sleep(5)  # Give the camera time to adjust
        ret, frame = cap.read()
        if not ret:
            cap.release()
            raise Exception("Failed to capture image from camera")
        
        print("Image captured successfully.")
        cap.release()
    return frame
