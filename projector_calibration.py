import cv2
import numpy as np
import time
import os

def is_raspberry_pi():
    """Check if the script is running on a Raspberry Pi."""
    try:
        with open("/sys/firmware/devicetree/base/model", "r") as f:
            return "raspberry pi" in f.read().lower()
    except Exception:
        return False

def calibrate(camera_calibration_file, pattern_size=(9, 6), square_size=1.0):
    """
    Calibrates a projector-camera system.

    This function displays a calibration pattern on the screen, captures an image
    from the camera, and calculates the perspective transformation matrix to map
    camera coordinates to screen coordinates.

    Args:
        camera_calibration_file (str): Path to the camera calibration file (.npz).
        pattern_size (tuple): The number of inner corners in the calibration pattern (width, height).
        square_size (float): The size of a square in the calibration pattern in some units.

    Returns:
        numpy.ndarray: The 3x3 perspective transformation matrix.
    """
    # Load camera calibration
    with np.load(camera_calibration_file) as data:
        camera_matrix = data['camera_matrix']
        dist_coeffs = data['dist_coeffs']

    # Create a window and display the calibration pattern
    cv2.namedWindow('pattern', cv2.WND_PROP_FULLSCREEN)
    cv2.setWindowProperty('pattern', cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)


    # Create the pattern image with a white border
    border_size = 100
    pattern_image = np.zeros(((pattern_size[1] * 100) + 2 * border_size, (pattern_size[0] * 100) + 2 * border_size, 3), dtype=np.uint8)
    pattern_image.fill(255) # Fill with white

    for i in range(pattern_size[1]):
        for j in range(pattern_size[0]):
            # Draw squares with offset for the border
            if (i + j) % 2 == 0:
                cv2.rectangle(pattern_image, (j * 100 + border_size, i * 100 + border_size), ((j + 1) * 100 + border_size, (i + 1) * 100 + border_size), (0, 0, 0), -1) # Black squares
            else:
                cv2.rectangle(pattern_image, (j * 100 + border_size, i * 100 + border_size), ((j + 1) * 100 + border_size, (i + 1) * 100 + border_size), (255, 255, 255), -1) # White squares
    
    cv2.imshow('pattern', pattern_image)
    cv2.waitKey(1000) # Wait for the window to appear

    # Capture an image from the camera
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

    cv2.destroyWindow('pattern')
    cv2.imwrite('captured_frame.jpg', frame)
    print("Captured frame saved as 'captured_frame.jpg'")


    # Find the pattern in the captured image
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    # The inner corners are calculated as the size - 1 in both dimensions.
    pattern_corners = (pattern_size[0] - 1, pattern_size[1] - 1)
    ret, corners = cv2.findChessboardCorners(gray, pattern_corners, None)

    if not ret:
        raise Exception("Chessboard not found in the captured image.")

    # Get the screen coordinates of the pattern corners
    screen_points = np.zeros((np.prod(pattern_corners), 2), np.float32)
    for i in range(pattern_corners[1]):
        for j in range(pattern_corners[0]):
            screen_points[i * pattern_corners[0] + j] = [j * 100 + 50 + border_size, i * 100 + 50 + border_size]


    # Get the camera coordinates of the pattern corners
    camera_points = corners.reshape(-1,2)

    # Calculate the perspective transformation matrix
    transformation_matrix, _ = cv2.findHomography(camera_points, screen_points)

    return transformation_matrix

if __name__ == '__main__':
    # Example usage
    matrix = calibrate('camera_calibration.npz')
    print("Transformation matrix:")
    print(matrix)
