import math
from typing import TYPE_CHECKING, Optional

import cv2
import numpy as np

from light_map.core.common_types import Token
from light_map.map.map_system import MapSystem
from light_map.rendering.projection import CameraProjectionModel
from light_map.vision.infrastructure.debug_utils import DebugVisualizer


if TYPE_CHECKING:
    from light_map.rendering.projection import Projector3DModel
    from light_map.rendering.projector import ProjectorDistortionModel


class FlashTokenDetector:
    # --- Flash Detection Parameters ---
    FLASH_GAUSSIAN_BLUR = (9, 9)
    FLASH_ADAPTIVE_BLOCK_SIZE = 101
    FLASH_ADAPTIVE_C = 10
    FLASH_MORPH_OPEN_ITER = 2
    FLASH_MORPH_CLOSE_ITER = 3
    FLASH_DISTANCE_THRESH = 10.0
    FLASH_MIN_BLOB_AREA = 300

    # --- Clustering & Result Parameters ---
    CONFIDENCE_SCALING = 3.0
    GRID_OVERLAP_THRESHOLD = 0.4

    def __init__(self, debug_mode: bool = False):
        self.debug_mode = debug_mode
        self.camera_matrix: np.ndarray | None = None
        self.distortion_coefficients: np.ndarray | None = None
        self.rotation_vector: np.ndarray | None = None
        self.translation_vector: np.ndarray | None = None
        self.projection_model: CameraProjectionModel | None = None

    def set_calibration(
        self, camera_matrix: np.ndarray, distortion_coefficients: np.ndarray
    ):
        self.camera_matrix = camera_matrix
        self.distortion_coefficients = distortion_coefficients
        self._update_projection_model()

    def set_extrinsics(
        self, rotation_vector: np.ndarray, translation_vector: np.ndarray
    ):
        self.rotation_vector = rotation_vector
        self.translation_vector = translation_vector
        self._update_projection_model()

    def _update_projection_model(self):
        """Updates the shared projection model if all calibration is present."""
        if (
            self.camera_matrix is not None
            and self.rotation_vector is not None
            and self.translation_vector is not None
        ):
            self.projection_model = CameraProjectionModel(
                self.camera_matrix,
                self.distortion_coefficients,
                self.rotation_vector,
                self.translation_vector,
            )

    def detect(
        self,
        frame_white: np.ndarray,
        projector_matrix: np.ndarray,
        map_system: MapSystem,
        grid_spacing_svg: float,
        grid_origin_x: float,
        grid_origin_y: float,
        mask_rois: list[tuple[int, int, int, int]] | None,
        ppi: float = 96.0,
        default_height_mm: float = 0.0,
        distortion_model: Optional["ProjectorDistortionModel"] = None,
        projector_3d_model: Optional["Projector3DModel"] = None,
    ) -> list[Token]:
        warped_image, markers = self._preprocess_and_find_markers(
            frame_white,
            projector_matrix,
            mask_rois,
            map_system.width,
            map_system.height,
        )
        tokens = self._extract_tokens_from_markers(
            warped_image,
            markers,
            projector_matrix,
            map_system,
            grid_spacing_svg,
            grid_origin_x,
            grid_origin_y,
            ppi=ppi,
            default_height_mm=default_height_mm,
            distortion_model=distortion_model,
            projector_3d_model=projector_3d_model,
        )
        if self.debug_mode:
            self._save_flash_debug_image(
                warped_image,
                markers,
                tokens,
                map_system,
                grid_spacing_svg,
                grid_origin_x,
                grid_origin_y,
            )
        return tokens

    def _preprocess_and_find_markers(
        self, frame_white, projector_matrix, mask_rois, target_w, target_h
    ):
        warped = cv2.warpPerspective(
            frame_white, projector_matrix, (target_w, target_h)
        )
        if mask_rois:
            for mx, my, mw, mh in mask_rois:
                cv2.rectangle(warped, (mx, my), (mx + mw, my + mh), (0, 0, 0), -1)
        gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, self.FLASH_GAUSSIAN_BLUR, 2)
        thresh = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            self.FLASH_ADAPTIVE_BLOCK_SIZE,
            self.FLASH_ADAPTIVE_C,
        )
        kernel = np.ones((3, 3), np.uint8)
        opening = cv2.morphologyEx(
            thresh, cv2.MORPH_OPEN, kernel, iterations=self.FLASH_MORPH_OPEN_ITER
        )
        closing = cv2.morphologyEx(
            opening,
            cv2.MORPH_CLOSE,
            np.ones((7, 7), np.uint8),
            iterations=self.FLASH_MORPH_CLOSE_ITER,
        )
        dist_transform = cv2.distanceTransform(closing, cv2.DIST_L2, 5)
        _, sure_fg = cv2.threshold(dist_transform, self.FLASH_DISTANCE_THRESH, 255, 0)
        sure_fg = np.uint8(sure_fg)
        unknown = cv2.subtract(cv2.dilate(closing, kernel, iterations=3), sure_fg)
        _, markers = cv2.connectedComponents(sure_fg)
        markers = markers + 1
        markers[unknown == 255] = 0
        return warped, cv2.watershed(warped, markers)

    def _extract_tokens_from_markers(
        self,
        warped_image,
        markers,
        projector_matrix,
        map_system,
        grid_spacing_svg,
        grid_origin_x,
        grid_origin_y,
        ppi=96.0,
        default_height_mm=0.0,
        distortion_model=None,
        projector_3d_model=None,
    ):
        tokens = []
        id_counter = 1
        found_cells = set()
        gray = cv2.cvtColor(warped_image, cv2.COLOR_BGR2GRAY)
        for marker_id in np.unique(markers):
            if marker_id <= 1:
                continue
            blob_mask = np.zeros_like(gray, dtype=np.uint8)
            blob_mask[markers == marker_id] = 255
            if cv2.countNonZero(blob_mask) < self.FLASH_MIN_BLOB_AREA:
                continue
            if grid_spacing_svg > 0:
                self._process_blob_with_grid(
                    blob_mask,
                    map_system,
                    grid_spacing_svg,
                    grid_origin_x,
                    grid_origin_y,
                    tokens,
                    found_cells,
                    id_counter,
                    default_height_mm=default_height_mm,
                    distortion_model=distortion_model,
                )
                id_counter = len(tokens) + 1
            else:
                self._process_blob_with_centroid(
                    blob_mask,
                    projector_matrix,
                    map_system,
                    tokens,
                    id_counter,
                    ppi=ppi,
                    default_height_mm=default_height_mm,
                    distortion_model=distortion_model,
                    projector_3d_model=projector_3d_model,
                )
                id_counter += 1
        return tokens

    def _process_blob_with_grid(
        self,
        blob_mask,
        map_system,
        spacing,
        ox,
        oy,
        tokens,
        found_cells,
        id_start,
        default_height_mm=0.0,
        distortion_model=None,
    ):
        x, y, w, h = cv2.boundingRect(blob_mask)
        pts = np.float32([[x, y], [x + w, y], [x, y + h], [x + w, y + h]]).reshape(
            -1, 1, 2
        )
        world_pts = []
        for p in pts:
            sx, sy = p[0]
            if distortion_model:
                sx, sy = distortion_model.correct_theoretical_point(sx, sy)
            world_pts.append(map_system.screen_to_world(sx, sy))

        min_gx = math.floor((min(p[0] for p in world_pts) - ox) / spacing) - 1
        max_gx = math.ceil((max(p[0] for p in world_pts) - ox) / spacing) + 1
        min_gy = math.floor((min(p[1] for p in world_pts) - oy) / spacing) - 1
        max_gy = math.ceil((max(p[1] for p in world_pts) - oy) / spacing) + 1

        bbox_mask = np.zeros_like(blob_mask)
        cv2.rectangle(bbox_mask, (x, y), (x + w, y + h), 255, -1)

        for gx in range(min_gx, max_gx):
            for gy in range(min_gy, max_gy):
                if (gx, gy) in found_cells:
                    continue
                cw_pts = [
                    (ox + gx * spacing, oy + gy * spacing),
                    (ox + (gx + 1) * spacing, oy + gy * spacing),
                    (ox + (gx + 1) * spacing, oy + (gy + 1) * spacing),
                    (ox + gx * spacing, oy + (gy + 1) * spacing),
                ]
                cs_pts = np.array(
                    [map_system.world_to_screen(p[0], p[1]) for p in cw_pts],
                    dtype=np.int32,
                )
                c_mask = np.zeros_like(blob_mask)
                cv2.fillConvexPoly(c_mask, cs_pts, 255)
                c_area = cv2.countNonZero(c_mask)
                if (
                    c_area > 0
                    and cv2.countNonZero(cv2.bitwise_and(bbox_mask, c_mask)) / c_area
                    > self.GRID_OVERLAP_THRESHOLD
                ):
                    wx = ox + (gx + 0.5) * spacing
                    wy = oy + (gy + 0.5) * spacing
                    tokens.append(
                        Token(
                            id=id_start + len(tokens),
                            world_x=wx,
                            world_y=wy,
                            world_z=0.0,
                            marker_x=wx,
                            marker_y=wy,
                            marker_z=default_height_mm,
                            grid_x=gx,
                            grid_y=gy,
                            confidence=1.0,
                        )
                    )
                    found_cells.add((gx, gy))

    def _process_blob_with_centroid(
        self,
        blob_mask,
        projector_matrix,
        map_system,
        tokens,
        id_counter,
        ppi=96.0,
        default_height_mm=0.0,
        distortion_model=None,
        projector_3d_model=None,
    ):
        moments = cv2.moments(blob_mask)
        if moments["m00"] > 0:
            screen_x, screen_y = (
                moments["m10"] / moments["m00"],
                moments["m01"] / moments["m00"],
            )

            if self.projection_model is not None:
                # 3D projection: Un-warp from projector to camera space
                # screen_x, screen_y are in Projector pixels (warped frame)
                # Use inverse homography to find camera (u, v)
                inv_homography = np.linalg.inv(projector_matrix)
                projector_point = np.array(
                    [screen_x, screen_y], dtype=np.float32
                ).reshape(1, 1, 2)
                camera_point = cv2.perspectiveTransform(
                    projector_point, inv_homography
                )[0][0]

                # Apply vertical projection (parallax correction)
                camera_pixels = camera_point.reshape(1, 2)
                world_points = self.projection_model.reconstruct_world_points(
                    camera_pixels, default_height_mm
                )
                world_x_mm, world_y_mm = world_points[0]

                if projector_3d_model and projector_3d_model.use_3d:
                    world_point_3d = np.array(
                        [[world_x_mm, world_y_mm, default_height_mm]], dtype=np.float32
                    )
                    projector_pixel_coord = (
                        projector_3d_model.project_world_to_projector(world_point_3d)[0]
                    )
                    px, py = projector_pixel_coord[0], projector_pixel_coord[1]
                else:
                    ppi_mm = ppi / 25.4
                    px = world_x_mm * ppi_mm
                    py = world_y_mm * ppi_mm

                    if distortion_model:
                        px, py = distortion_model.correct_theoretical_point(px, py)

                wx, wy = map_system.screen_to_world(px, py)
            else:
                # Fallback to simple 2D projection
                if distortion_model:
                    screen_x, screen_y = distortion_model.correct_theoretical_point(
                        screen_x, screen_y
                    )
                wx, wy = map_system.screen_to_world(screen_x, screen_y)

            tokens.append(
                Token(
                    id=id_counter + len(tokens),
                    world_x=wx,
                    world_y=wy,
                    world_z=0.0,
                    marker_x=wx,
                    marker_y=wy,
                    marker_z=default_height_mm,
                    confidence=1.0,
                )
            )

    def _save_flash_debug_image(
        self,
        warped_image,
        markers,
        tokens,
        map_system,
        grid_spacing_svg,
        grid_origin_x,
        grid_origin_y,
    ):
        debug_img = warped_image.copy()

        # Draw Grid if applicable
        if grid_spacing_svg > 0:
            DebugVisualizer.draw_grid(
                debug_img, map_system, grid_spacing_svg, grid_origin_x, grid_origin_y
            )

        # Draw Markers
        unique_markers = np.unique(markers)
        for marker_id in unique_markers:
            if marker_id <= 1:
                continue
            blob_mask = np.zeros(markers.shape, dtype=np.uint8)
            blob_mask[markers == marker_id] = 255
            contours, _ = cv2.findContours(
                blob_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            if contours:
                cv2.drawContours(debug_img, contours, -1, (0, 255, 0), 1)
                x, y, wr, hr = cv2.boundingRect(contours[0])
                cv2.rectangle(debug_img, (x, y), (x + wr, y + hr), (255, 0, 0), 1)

        DebugVisualizer.draw_tokens(debug_img, tokens, map_system)
        DebugVisualizer.save_debug_image("debug_token_detection_flash", debug_img)
