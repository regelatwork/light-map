from collections.abc import Callable
from typing import Any

import cv2
import numpy as np

from light_map.core.common_types import GmPosition


class HandMasker:
    """Handles both Input Masking (filtering hands) and Projection Masking (Digital Shadow)."""

    def __init__(self, persistence_seconds: float = 1.0):
        self.persistence_seconds = persistence_seconds
        self.last_hulls: list[np.ndarray] = []
        self.last_detection_time = 0.0
        self._cached_mask: Any = None
        self._cached_hulls_hash: int = -1
        self._cached_params: tuple[int, int, int, int] = (-1, -1, -1, -1)

    def is_point_masked(
        self, x: int, y: int, gm_position: GmPosition, resolution: tuple[int, int]
    ) -> bool:
        """
        Checks if a point (in projector space) should be masked (ignored)
        based on the GM's position.
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

    def get_mask_hulls(
        self,
        multi_hand_landmarks: list[Any],
        transformation_fn: Callable[[np.ndarray], np.ndarray],
        current_time: float,
    ) -> list[np.ndarray]:
        """
        High-level API for HandMaskLayer.
        Returns hulls in projector space, respecting persistence.
        """
        return self.compute_hulls(multi_hand_landmarks, transformation_fn, current_time)

    def compute_hulls(
        self,
        multi_hand_landmarks: list[Any],
        transformation_fn: Callable[[np.ndarray], np.ndarray],
        current_time: float,
    ) -> list[np.ndarray]:
        """
        Computes convex hulls for multiple hands in projector space.
        transformation_fn: maps (N, 2) normalized landmarks to (N, 2) projector pixels.
        """
        if not multi_hand_landmarks:
            if current_time - self.last_detection_time <= self.persistence_seconds:
                return self.last_hulls
            else:
                self.last_hulls = []
                return []

        self.last_detection_time = current_time
        hulls = []
        for landmarks in multi_hand_landmarks:
            if hasattr(landmarks, "landmark"):
                # MediaPipe-style object
                pts = np.array(
                    [[lm.x, lm.y] for lm in landmarks.landmark], dtype=np.float32
                )
            elif isinstance(landmarks, list):
                # Serialized list of dicts (IPC format)
                pts = np.array(
                    [[lm["x"], lm["y"]] for lm in landmarks], dtype=np.float32
                )
            else:
                continue

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

            hulls.append(hull_pts)

        self.last_hulls = hulls
        return hulls

    def _hash_hulls(self, hulls: list[np.ndarray]) -> int:
        if not hulls:
            return 0
        h_val = 0
        for hull in hulls:
            h_val ^= hash(hull.tobytes())
        return h_val

    def generate_mask_image(
        self,
        hulls: list[np.ndarray],
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
            cv2.drawContours(mask, hulls, -1, 255, thickness=padding * 2)
        cv2.fillPoly(mask, hulls, 255)

        self._cached_mask = mask
        self._cached_hulls_hash = current_hash
        self._cached_params = current_params
        return mask
