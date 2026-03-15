from typing import List, Optional, Tuple
import numpy as np
import cv2
from .common_types import Layer, ImagePatch, LayerMode


class Projector3DCalibrationLayer(Layer):
    """
    Renders the calibration grid for 3D projector calibration.
    Displays a grid of ArUco markers and informational text.
    """

    def __init__(
        self,
        width: int,
        height: int,
        box_markers: List[Tuple[int, np.ndarray]] = None,
        table_markers: List[Tuple[int, np.ndarray]] = None,
        instructions: str = "",
    ):
        super().__init__(is_static=False, layer_mode=LayerMode.BLOCKING)
        self.width = width
        self.height = height
        self.box_markers = box_markers or []
        self.table_markers = table_markers or []
        self.instructions = instructions
        self._is_dynamic = True
        self._aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)

    def get_current_version(self) -> int:
        return int(np.random.randint(0, 1000000))

    def _generate_patches(self, current_time: float) -> List[ImagePatch]:
        # Create full black background
        img = np.zeros((self.height, self.width, 4), dtype=np.uint8)
        img[:, :, 3] = 255  # Fully opaque black

        # Draw Table Markers (Reference)
        for aruco_id, corners in self.table_markers:
            self._draw_marker(img, aruco_id, corners, (0, 255, 0))  # Green for table

        # Draw Box Markers (Target)
        for aruco_id, corners in self.box_markers:
            self._draw_marker(img, aruco_id, corners, (0, 255, 255))  # Yellow for box

        # Draw Instructions
        if self.instructions:
            from .display_utils import draw_text_with_background

            draw_text_with_background(
                img,
                self.instructions,
                (50, 50),
                scale=1.0,
                thickness=2,
                color=(255, 255, 255),
            )

        return [ImagePatch(0, 0, self.width, self.height, img)]

    def _draw_marker(self, img, aruco_id, corners, color):
        # corners is (4, 2) in projector pixels
        marker_size = int(np.linalg.norm(corners[0] - corners[1]))
        if marker_size < 10:
            return

        # Generate the marker bits
        marker_img = cv2.aruco.generateImageMarker(self._aruco_dict, aruco_id, marker_size)
        marker_bgr = cv2.cvtColor(marker_img, cv2.COLOR_GRAY2BGR)

        # Create a white border/background for contrast
        padded_marker = np.full(
            (marker_size + 4, marker_size + 4, 3), 255, dtype=np.uint8
        )
        padded_marker[2 : 2 + marker_size, 2 : 2 + marker_size] = marker_bgr

        # Warp marker to the designated corners
        src_pts = np.array(
            [
                [0, 0],
                [marker_size + 4, 0],
                [marker_size + 4, marker_size + 4],
                [0, marker_size + 4],
            ],
            dtype=np.float32,
        )
        # Add slight padding to the target corners to match the border
        M = cv2.getPerspectiveTransform(src_pts, corners.astype(np.float32))

        # We warp onto a temporary layer then composite
        temp = cv2.warpPerspective(padded_marker, M, (self.width, self.height))

        # Composite (simple max or addition since base is black)
        mask = (temp > 0).any(axis=2)
        img[mask, :3] = temp[mask]
        
        # Draw ID for debugging/info
        center = np.mean(corners, axis=0).astype(int)
        cv2.putText(
            img,
            str(aruco_id),
            (center[0], center[1]),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            1,
        )
