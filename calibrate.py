
import cv2
import numpy as np
import os
import glob

# Define the dimensions of the checkerboard
CHECKERBOARD = (6, 9)

# Stop the iteration when specified
# accuracy, epsilon, is reached or
# specified number of iterations are completed.
criteria = (cv2.TERM_CRITERIA_EPS +
            cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

# Vector for 3D points
threedpoints = []

# Vector for 2D points
twodpoints = []

# 3D points real world coordinates
threedp = np.zeros((1, CHECKERBOARD[0]
                    * CHECKERBOARD[1],
                    3), np.float32)
threedp[0, :, :2] = np.mgrid[0:CHECKERBOARD[0],
                                0:CHECKERBOARD[1]].T.reshape(-1, 2)

# Extracting path of individual image stored
# in a given directory. Since no path is
# specified, it will take current directory
# jpg files alone
images = glob.glob('./images/*.jpg')

if not images:
    print("No images found in the 'images' directory. Please add your chessboard calibration images.")
else:
    for filename in images:
        image = cv2.imread(filename)
        grayColor = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Find the chess board corners
        # If desired number of corners are
        # found in the image then ret = true
        ret, corners = cv2.findChessboardCorners(
                        grayColor, CHECKERBOARD,
                        cv2.CALIB_CB_ADAPTIVE_THRESH
                        + cv2.CALIB_CB_FAST_CHECK +
                        cv2.CALIB_CB_NORMALIZE_IMAGE)

        # If desired number of corners can be detected then,
        # refine the pixel coordinates and display
        # them on the images of checker board
        if ret == True:
            threedpoints.append(threedp)

            # Refining pixel coordinates
            # for given 2d points.
            corners2 = cv2.cornerSubPix(
                grayColor, corners, (11, 11), (-1, -1), criteria)

            twodpoints.append(corners2)

            # Draw and display the corners
            image = cv2.drawChessboardCorners(image,
                                              CHECKERBOARD,
                                              corners2, ret)

        cv2.imshow('img', image)
        cv2.waitKey(0)

    cv2.destroyAllWindows()

    if threedpoints:
        # Perform camera calibration by
        # passing the value of above found out 3D points (threedpoints)
        # and its corresponding pixel coordinates of the
        # detected corners (twodpoints)
        ret, matrix, distortion, r_vecs, t_vecs = cv2.calibrateCamera(
            threedpoints, twodpoints, grayColor.shape[::-1], None, None)

        # Displaying required output
        print(" Camera matrix:")
        print(matrix)

        print("\n Distortion coefficient:")
        print(distortion)

        # Save the camera matrix and distortion coefficients to a file
        np.savez('camera_calibration.npz', camera_matrix=matrix, dist_coeffs=distortion)
    else:
        print("No chessboard corners found in any of the images. Calibration failed.")
