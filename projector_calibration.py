import cv2
import numpy as np
import time

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


    # Generate the calibration pattern
    pattern_points = np.zeros((np.prod(pattern_size), 3), np.float32)
    pattern_points[:, :2] = np.mgrid[0:pattern_size[0], 0:pattern_size[1]].T.reshape(-1, 2)
    pattern_points *= square_size
    
    # Create the pattern image
    pattern_image = np.zeros((pattern_size[1]*100, pattern_size[0]*100, 3), dtype=np.uint8)
    for i in range(pattern_size[1]):
        for j in range(pattern_size[0]):
            if (i+j)%2 == 0:
                cv2.rectangle(pattern_image, (j*100, i*100), ((j+1)*100, (i+1)*100), (255,255,255), -1)
    
    cv2.imshow('pattern', pattern_image)
    cv2.waitKey(1000) # Wait for the window to appear

    # Capture an image from the camera
    cap = cv2.VideoCapture(0)
    time.sleep(2) # Give the camera time to adjust
    ret, frame = cap.read()
    if not ret:
        raise Exception("Failed to capture image from camera")
    cap.release()
    cv2.destroyWindow('pattern')


    # Find the pattern in the captured image
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    ret, corners = cv2.findChessboardCorners(gray, pattern_size, None)

    if not ret:
        raise Exception("Chessboard not found in the captured image.")

    # Get the screen coordinates of the pattern corners
    screen_points = np.zeros((np.prod(pattern_size), 2), np.float32)
    for i in range(pattern_size[1]):
        for j in range(pattern_size[0]):
            screen_points[i*pattern_size[0]+j] = [j*100+50, i*100+50]


    # Get the camera coordinates of the pattern corners
    camera_points = corners.reshape(-1,2)

    # Calculate the perspective transformation matrix
    transformation_matrix, _ = cv2.findHomography(camera_points, screen_points)

    return transformation_matrix

if __name__ == '__main__':
    # Example usage
    try:
        matrix = calibrate('camera_calibration.npz')
        print("Transformation matrix:")
        print(matrix)
    except Exception as e:
        print(f"Error: {e}")
