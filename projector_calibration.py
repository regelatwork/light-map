import sys
import os
import cv2
import numpy as np

# Ensure we can import the local package
sys.path.insert(0, os.path.abspath("src"))

from light_map.camera import Camera
from light_map.projector import generate_calibration_pattern, compute_projector_homography

def calibrate(camera_calibration_file, rows=6, cols=9, width=1920, height=1080):
    # Load camera calibration (optional, if we want to undistort first, but 
    # findHomography works on raw points too for planar surfaces usually)
    if os.path.exists(camera_calibration_file):
        print(f"Loading camera calibration from {camera_calibration_file}...")
        with np.load(camera_calibration_file) as data:
            mtx = data['camera_matrix']
            dist = data['dist_coeffs']
    else:
        print("Warning: Camera calibration file not found. Proceeding without it.")

    # Setup Fullscreen Window
    window_name = 'pattern'
    cv2.namedWindow(window_name, cv2.WND_PROP_FULLSCREEN)
    cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    # Generate Pattern
    pattern_img, params = generate_calibration_pattern(width, height, rows, cols)
    
    cv2.imshow(window_name, pattern_img)
    print("Displaying pattern. Waiting 2 seconds for projector/camera to settle...")
    cv2.waitKey(2000)

    # Capture Image
    print("Capturing image...")
    # Initialize camera using the new class (handles lifecycle correctly)
    with Camera() as cam:
        # Read a few frames to let auto-exposure settle
        for _ in range(10):
            cam.read()
        frame = cam.read()

    if frame is None:
        print("Failed to capture image.")
        return None

    cv2.destroyWindow(window_name)
    
    # Save debug image
    cv2.imwrite('captured_frame.jpg', frame)
    print("Saved capture to captured_frame.jpg")

    # Compute Homography
    try:
        matrix = compute_projector_homography(frame, params)
        return matrix
    except Exception as e:
        print(f"Error computing homography: {e}")
        return None

if __name__ == '__main__':
    projector_width = 1920
    projector_height = 1080
    
    matrix = calibrate('camera_calibration.npz', width=projector_width, height=projector_height)
    
    if matrix is not None:
        print("Transformation matrix:")
        print(matrix)
        
        output_file = 'projector_calibration.npz'
        print(f"Saving calibration to {output_file}...")
        np.savez(output_file, projector_matrix=matrix, resolution=np.array([projector_width, projector_height]))
        print("Saved successfully.")