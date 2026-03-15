import cv2
import numpy as np
import math
from typing import List, Tuple, Optional, TYPE_CHECKING
from light_map.common_types import Token
from light_map.map_system import MapSystem
from light_map.vision.debug_utils import DebugVisualizer

if TYPE_CHECKING:
    from light_map.projector import ProjectorDistortionModel
    from light_map.vision.projector import Projector3DModel


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
        self.camera_matrix = None
        self.dist_coeffs = None
        self.rvec = None
        self.tvec = None
        self.R = None
        self.camera_center_world = None

    def set_calibration(self, camera_matrix: np.ndarray, dist_coeffs: np.ndarray):
        self.camera_matrix = camera_matrix
        self.dist_coeffs = dist_coeffs

    def set_extrinsics(self, rvec: np.ndarray, tvec: np.ndarray):
        self.rvec = rvec
        self.tvec = tvec
        if self.rvec is not None and self.tvec is not None:
            self.R, _ = cv2.Rodrigues(self.rvec)
            self.camera_center_world = -self.R.T @ self.tvec.flatten()

    def detect(
        self,
        frame_white: np.ndarray,
        projector_matrix: np.ndarray,
        map_system: MapSystem,
        grid_spacing_svg: float,
        grid_origin_x: float,
        grid_origin_y: float,
        mask_rois: Optional[List[Tuple[int, int, int, int]]],
        ppi: float = 96.0,
        default_height_mm: float = 0.0,
        distortion_model: Optional["ProjectorDistortionModel"] = None,
        projector_3d_model: Optional["Projector3DModel"] = None,
    ) -> List[Token]:
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
        M = cv2.moments(blob_mask)
        if M["m00"] > 0:
            sx, sy = M["m10"] / M["m00"], M["m01"] / M["m00"]

            if self.camera_matrix is not None and self.R is not None:
                # 3D projection: Un-warp from projector to camera space
                # sx, sy are in Projector pixels (warped frame)
                # Use inverse homography to find camera (u, v)
                inv_h = np.linalg.inv(projector_matrix)
                p_proj = np.array([sx, sy], dtype=np.float32).reshape(1, 1, 2)
                p_cam = cv2.perspectiveTransform(p_proj, inv_h)[0][0]
                u, v = p_cam[0], p_cam[1]

                # Apply vertical projection
                wx_mm, wy_mm = self._parallax_correction(u, v, default_height_mm)

                if projector_3d_model and projector_3d_model.use_3d:
                    p_world = np.array(
                        [[wx_mm, wy_mm, default_height_mm]], dtype=np.float32
                    )
                    p_proj_real = projector_3d_model.project_world_to_projector(
                        p_world
                    )[0]
                    px, py = p_proj_real[0], p_proj_real[1]
                else:
                    ppi_mm = ppi / 25.4
                    px = wx_mm * ppi_mm
                    py = wy_mm * ppi_mm

                    if distortion_model:
                        px, py = distortion_model.correct_theoretical_point(px, py)

                wx, wy = map_system.screen_to_world(px, py)
            else:
                # Fallback to simple 2D projection
                if distortion_model:
                    sx, sy = distortion_model.correct_theoretical_point(sx, sy)
                wx, wy = map_system.screen_to_world(sx, sy)

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

    def _parallax_correction(self, u: float, v: float, h: float) -> Tuple[float, float]:
        """
        Intersects the ray from camera through (u, v) with the plane z = h.
        Returns (X, Y) in world space.
        """
        if self.camera_matrix is None or self.R is None:
            # Fallback if no 3D pose is available
            return 0.0, 0.0

        # 1. Back-project to ray in camera space
        p_pixel = np.array([u, v, 1.0]).reshape(3, 1)
        ray_cam = np.linalg.inv(self.camera_matrix) @ p_pixel

        # 2. Transform ray to world space
        v_world = self.R.T @ ray_cam
        v_world = v_world.flatten()

        # 3. Intersect with plane z = h
        cz = self.camera_center_world[2]
        vz = v_world[2]

        if abs(vz) < 1e-6:
            return 0.0, 0.0

        s = (h - cz) / vz
        if s < 0:
            return 0.0, 0.0

        p_world = self.camera_center_world + s * v_world
        return p_world[0], p_world[1]
