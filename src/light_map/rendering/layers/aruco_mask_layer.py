from typing import Any

import cv2
import numpy as np

from light_map.core.common_types import AppConfig, ImagePatch, Layer, LayerMode
from light_map.core.constants import DEFAULT_TOKEN_HEIGHT_MM
from light_map.rendering.projection import ProjectionService
from light_map.state.world_state import WorldState


class ArucoMaskLayer(Layer):
    """
    Renders solid grey patches over detected ArUco markers to stabilize vision.
    Prevents map content from interfering with marker recognition.
    Uses ProjectionService for parallax-corrected 3D mapping.
    """

    def __init__(
        self,
        state: WorldState,
        config: AppConfig,
        projection_service: ProjectionService | None = None,
    ):
        super().__init__(state=state, is_static=False, layer_mode=LayerMode.MASKED)
        self.config = config
        self.projection_service = projection_service
        self.last_corners: dict[int, np.ndarray] = {}
        self.last_seen: dict[int, float] = {}

    def get_current_version(self) -> int:
        if self.state is None:
            return 0

        # Include enable_aruco_masking change in version
        enabled_bit = 1 if self.config.enable_aruco_masking else 0

        # Use raw_aruco_version to ensure masks persist even if logical tokens change.
        # Include grid metadata and viewport for 3D projection stability.
        # NEW: Include projector_pose_version and general config_version for manual adjustment feedback.
        v = max(
            self.state.raw_aruco_version,
            self.state.grid_metadata_version,
            self.state.viewport_version,
            self.state.projector_pose_version,
            self.state.config_version,
        )

        # Only include system_time_version if there are lingering masks being timed out.
        # If all masks are currently visible, raw_aruco_version handles updates.
        current_ids = set(self.state.raw_aruco.get("ids", []))
        has_lingering = any(
            marker_id not in current_ids for marker_id in self.last_seen
        )

        if has_lingering:
            v = max(v, self.state.system_time_version)

        return (v << 1) | enabled_bit

    def _transform_pts(
        self,
        camera_pixels: Any,
        height_mm: float = 0.0,
        prefer_homography: bool = True,
    ) -> np.ndarray:
        """
        Transforms camera pixel points to projector space.
        Uses ProjectionService if available, otherwise falls back to homography.
        """
        if isinstance(camera_pixels, list):
            camera_pixels = np.array(camera_pixels, dtype=np.float32)
        else:
            camera_pixels = camera_pixels.astype(np.float32)

        if self.projection_service:
            return self.projection_service.project_camera_to_projector(
                camera_pixels,
                height_mm=height_mm,
                prefer_homography=prefer_homography,
                projector_pose=self.state.projector_pose if self.state else None,
            )

        # Fallback to standard surface homography (Z=0)
        camera_pixels_reshaped = camera_pixels.reshape(-1, 1, 2).astype(np.float32)
        if self.config.distortion_model:
            proj_pts = self.config.distortion_model.apply_correction(
                camera_pixels_reshaped
            )
        else:
            proj_pts = cv2.perspectiveTransform(
                camera_pixels_reshaped, self.config.projector_matrix
            )
        return proj_pts.reshape(-1, 2)

    def _generate_patches(self, current_time: float) -> list[ImagePatch]:
        if not self.config.enable_aruco_masking or self.state is None:
            return []

        raw_aruco = self.state.raw_aruco
        corners_list = raw_aruco.get("corners", [])
        ids = raw_aruco.get("ids", [])

        # Update persistent store
        for i, marker_id in enumerate(ids):
            if i < len(corners_list):
                self.last_corners[marker_id] = np.array(
                    corners_list[i], dtype=np.float32
                )
                self.last_seen[marker_id] = current_time

        # Cleanup and collect markers to render
        to_render = []
        ids_to_remove = []
        persistence_s = self.config.aruco_mask_persistence_s

        for marker_id, last_time in self.last_seen.items():
            if current_time - last_time <= persistence_s:
                to_render.append((marker_id, self.last_corners[marker_id]))
            else:
                ids_to_remove.append(marker_id)

        for marker_id in ids_to_remove:
            del self.last_seen[marker_id]
            if marker_id in self.last_corners:
                del self.last_corners[marker_id]

        if not to_render:
            return []

        patches = []
        padding = self.config.aruco_mask_padding
        intensity = self.config.aruco_mask_intensity
        color = (intensity, intensity, intensity, 255)

        # Projector resolution for clamping
        limit_w = self.config.width
        limit_h = self.config.height

        default_height = DEFAULT_TOKEN_HEIGHT_MM

        for marker_id, corners in to_render:
            # Determine height
            height_mm = default_height
            if marker_id != -1 and marker_id in getattr(
                self.config, "aruco_defaults", {}
            ):
                defn = self.config.aruco_defaults[marker_id]
                # Priority: 1. Specific height_mm, 2. Profile height_mm, 3. Default
                specific_height = getattr(defn, "height_mm", None)
                profile_name = getattr(defn, "profile", None)

                if specific_height is not None:
                    height_mm = specific_height
                elif profile_name in getattr(self.config, "token_profiles", {}):
                    height_mm = self.config.token_profiles[profile_name].height_mm

            # corners is (4, 2) in camera pixel coordinates.
            # We target the actual height of the token for mask projection.
            # We prefer homography for masking because it's usually better calibrated for the tabletop.
            projector_corners = self._transform_pts(
                corners, height_mm=height_mm, prefer_homography=True
            )
            projector_corners = np.array(projector_corners, dtype=np.float32).reshape(
                -1, 2
            )

            # Get bounding box in projector space
            x, y, w, h = cv2.boundingRect(projector_corners)

            x1 = max(0, x - padding)
            y1 = max(0, y - padding)
            x2 = min(limit_w, x + w + padding)
            y2 = min(limit_h, y + h + padding)

            patch_w, patch_h = int(x2 - x1), int(y2 - y1)
            if patch_w <= 0 or patch_h <= 0:
                continue

            # Local coordinates for the patch
            local_corners = projector_corners - [x1, y1]

            # Create patch data (BGRA)
            patch_data = np.zeros((patch_h, patch_w, 4), dtype=np.uint8)

            # Draw polygon on a mask
            mask = np.zeros((patch_h, patch_w), dtype=np.uint8)
            cv2.fillConvexPoly(mask, local_corners.astype(np.int32), 255)

            if padding > 0:
                kernel = cv2.getStructuringElement(
                    cv2.MORPH_ELLIPSE, (padding * 2 + 1, padding * 2 + 1)
                )
                mask = cv2.dilate(mask, kernel)

            # Set color and alpha
            patch_data[mask > 0, :3] = color[:3]
            patch_data[mask > 0, 3] = color[3]

            patches.append(
                ImagePatch(
                    x=int(x1), y=int(y1), width=patch_w, height=patch_h, data=patch_data
                )
            )

        return patches
