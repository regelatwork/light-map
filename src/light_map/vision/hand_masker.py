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
        self._cached_mask: Any = None
        self._cached_hulls_hash: int = -1
        self._cached_params: Tuple[int, int, int, int] = (-1, -1, -1, -1)

    def is_point_masked(
        self, x: int, y: int, gm_position: GmPosition, resolution: Tuple[int, int]
    ) -> bool:
        """
        Checks if a point (in projector space) should be masked (ignored)
        based on the GM's position.

        New Approach:
        1. Points INSIDE the projector area (0,0 to w,h) are NEVER masked.
        2. Points OUTSIDE are masked, unless they are on the GM's side.
        """
        w, h = resolution

        # 1. Inside is always interactive
        if 0 <= x < w and 0 <= y < h:
            return False

        # 2. Outside masking
        if gm_position == GmPosition.NONE:
            return True  # Mask everything outside if no GM position set

        is_north = y < 0
        is_south = y >= h
        is_west = x < 0
        is_east = x >= w

        # Check if the point is on an allowed side based on GM position
        if gm_position == GmPosition.NORTH:
            return not is_north
        if gm_position == GmPosition.SOUTH:
            return not is_south
        if gm_position == GmPosition.WEST:
            return not is_west
        if gm_position == GmPosition.EAST:
            return not is_east

        if gm_position == GmPosition.NORTH_WEST:
            return not (is_north or is_west)
        if gm_position == GmPosition.NORTH_EAST:
            return not (is_north or is_east)
        if gm_position == GmPosition.SOUTH_WEST:
            return not (is_south or is_west)
        if gm_position == GmPosition.SOUTH_EAST:
            return not (is_south or is_east)

        return True

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

            # Approximate hull to reduce points
            epsilon = 0.005 * cv2.arcLength(hull_pts, True)
            approx_hull = cv2.approxPolyDP(hull_pts, epsilon, True)
            hull_pts = approx_hull.reshape(-1, 2)

            # Apply padding (simple scaling or offsetting?)
            # For now, let's just use the hull as is, or maybe dilate later in the mask.
            # Dilation in mask space is easier and more robust.
            hulls.append(hull_pts)

        self.last_hulls = hulls
        return hulls

    def _hash_hulls(self, hulls: List[np.ndarray]) -> int:
        if not hulls:
            return 0
        # Fast hash using array bytes
        h_val = 0
        for hull in hulls:
            h_val ^= hash(hull.tobytes())
        return h_val

    def generate_mask_image(
        self,
        hulls: List[np.ndarray],
        width: int,
        height: int,
        padding: int = 0,
        blur: int = 0,
    ) -> np.ndarray:
        """Generates a binary mask image (255 for masked areas)."""
        current_hash = self._hash_hulls(hulls)
        current_params = (width, height, padding, blur)

        if (
            self._cached_mask is not None
            and self._cached_hulls_hash == current_hash
            and self._cached_params == current_params
        ):
            return self._cached_mask

        mask = np.zeros((height, width), dtype=np.uint8)

        if not hulls:
            self._cached_mask = mask
            self._cached_hulls_hash = current_hash
            self._cached_params = current_params
            return mask

        if padding > 0:
            # Draw thick boundaries to simulate dilation (much faster than cv2.dilate on large images)
            cv2.drawContours(mask, hulls, -1, 255, thickness=padding * 2)
        cv2.fillPoly(mask, hulls, 255)

        if blur > 0:
            # Ensure blur is odd
            b = blur if blur % 2 == 1 else blur + 1
            mask = cv2.GaussianBlur(mask, (b, b), 0)

        self._cached_mask = mask
        self._cached_hulls_hash = current_hash
        self._cached_params = current_params
        return mask
