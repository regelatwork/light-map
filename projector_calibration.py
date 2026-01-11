import cv2
import numpy as np
import time
from camera import capture_image

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
    frame = capture_image()

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
