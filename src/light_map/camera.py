import cv2
import time
import os

class Camera:
    """
    A wrapper around cv2.VideoCapture to handle different camera sources
    (standard webcam vs Raspberry Pi GStreamer).
    """

    def __init__(self, index=0, width=1920, height=1080, framerate=8):
        self.index = index
        self.width = width
        self.height = height
        self.framerate = framerate
        self.cap = None
        self._initialize_camera()

    def _is_raspberry_pi(self):
        """Check if the script is running on a Raspberry Pi."""
        try:
            with open("/sys/firmware/devicetree/base/model", "r") as f:
                return "raspberry pi" in f.read().lower()
        except Exception:
            return False

    def _get_gstreamer_pipeline(self):
        """
        Returns a GStreamer pipeline string for capturing from a specific Raspberry Pi camera.
        """
        # Note: This hardcoded path might need to be configurable in the future
        camera_name = "/base/axi/pcie@1000120000/rp1/i2c@88000/imx708@1a"
        
        return (
            f"libcamerasrc camera-name={camera_name} ! "
            f"video/x-raw, format=BGR, width=2304, height=1296, framerate={self.framerate}/1 ! "
            f"videoconvert ! "
            f"videoscale ! "
            f"video/x-raw, width={self.width}, height={self.height}, format=BGR ! "
            f"appsink drop=true sync=false"
        )

    def _initialize_camera(self):
        if self._is_raspberry_pi():
            print("Raspberry Pi detected. Using GStreamer pipeline.")
            pipeline = self._get_gstreamer_pipeline()
            # print(f"Pipeline: {pipeline}") # Debug
            self.cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
        else:
            print(f"Opening standard camera index {self.index}...")
            self.cap = cv2.VideoCapture(self.index)

        if not self.cap.isOpened():
            raise RuntimeError("Failed to open camera.")

    def read(self):
        """
        Reads a frame from the camera.
        Returns:
            frame: The captured frame, or None if error/end of stream.
        """
        if self.cap is None or not self.cap.isOpened():
            raise RuntimeError("Camera is not open.")
        
        ret, frame = self.cap.read()
        if not ret:
            return None
        return frame

    def release(self):
        """Releases the camera resource."""
        if self.cap:
            self.cap.release()
            self.cap = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
