import cv2
import numpy as np
from typing import List, Tuple, Any
from light_map.common_types import GmPosition


class HandMasker:
    """Handles both Input Masking (filtering hands) and Projection Masking (Digital Shadow)."""

    def __init__(self, persistence_frames: int = 3):
        self.persistence_frames = persistence_frames
        self.last_hulls: List[np.ndarray] = []
        self.frames_since_detection = 0

    def is_point_masked(
        self, x: int, y: int, gm_position: GmPosition, resolution: Tuple[int, int]
    ) -> bool:
        """
        Checks if a point (in projector space) should be masked (ignored)
        based on the GM's position.
        """
        if gm_position == GmPosition.NONE:
            return False

        w, h = resolution
        mid_x = w // 2
        mid_y = h // 2

        if gm_position == GmPosition.NORTH:
            return y > mid_y
        if gm_position == GmPosition.SOUTH:
            return y < mid_y
        if gm_position == GmPosition.WEST:
            return x > mid_x
        if gm_position == GmPosition.EAST:
            return x < mid_x

        if gm_position == GmPosition.NORTH_WEST:
            return x > mid_x or y > mid_y
        if gm_position == GmPosition.NORTH_EAST:
            return x < mid_x or y > mid_y
        if gm_position == GmPosition.SOUTH_WEST:
            return x > mid_x or y < mid_y
        if gm_position == GmPosition.SOUTH_EAST:
            return x < mid_x or y < mid_y

        return False

    def compute_hulls(
        self, multi_hand_landmarks: List[Any], transformation_fn: Any, padding: int = 0
    ) -> List[np.ndarray]:
        """
        Computes convex hulls for multiple hands in projector space.
        transformation_fn: maps (N, 2) normalized landmarks to (N, 2) projector pixels.
        """
        if not multi_hand_landmarks:
            self.frames_since_detection += 1
            if self.frames_since_detection <= self.persistence_frames:
                return self.last_hulls
            else:
                self.last_hulls = []
                return []

        self.frames_since_detection = 0
        hulls = []
        for landmarks in multi_hand_landmarks:
            pts = np.array(
                [[lm.x, lm.y] for lm in landmarks.landmark], dtype=np.float32
            )

            # Transform to projector space
            proj_pts = transformation_fn(pts)

            # Compute convex hull
            hull_indices = cv2.convexHull(
                proj_pts.astype(np.float32), returnPoints=False
            )
            hull_pts = proj_pts[hull_indices.flatten()].astype(np.int32)

            # Apply padding (simple scaling or offsetting?)
            # For now, let's just use the hull as is, or maybe dilate later in the mask.
            # Dilation in mask space is easier and more robust.
            hulls.append(hull_pts)

        self.last_hulls = hulls
        return hulls

    def generate_mask_image(
        self,
        hulls: List[np.ndarray],
        width: int,
        height: int,
        padding: int = 0,
        blur: int = 0,
    ) -> np.ndarray:
        """Generates a binary mask image (255 for masked areas)."""
        mask = np.zeros((height, width), dtype=np.uint8)

        if not hulls:
            return mask

        cv2.fillPoly(mask, hulls, 255)

        if padding > 0:
            kernel = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE, (padding * 2 + 1, padding * 2 + 1)
            )
            mask = cv2.dilate(mask, kernel)

        if blur > 0:
            # Ensure blur is odd
            b = blur if blur % 2 == 1 else blur + 1
            mask = cv2.GaussianBlur(mask, (b, b), 0)

        return mask
