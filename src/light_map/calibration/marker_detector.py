"""
Module for detecting ArUco markers in images.
"""

import cv2
import numpy as np


class MarkerDetector:
    def __init__(self, dictionary_id: int = 50):
        # DICT_4X4_50 is 50
        self.aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        self.parameters = cv2.aruco.DetectorParameters()
        self.detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.parameters)

    def detect(self, image: np.ndarray) -> list[tuple[int, np.ndarray]]:
        """
        Detects markers in the image.

        Returns:
            A list of tuples (id, corners)
        """
        corners, ids, _ = self.detector.detectMarkers(image)

        results = []
        if ids is not None:
            for i, id_list in enumerate(ids.flatten()):
                results.append((int(id_list), corners[i].reshape(-1, 2)))
        return results
