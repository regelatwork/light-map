import cv2
import numpy as np
import math
from typing import List, Tuple, Optional, TYPE_CHECKING
from light_map.common_types import Token
from light_map.map_system import MapSystem
from light_map.vision.debug_utils import DebugVisualizer

if TYPE_CHECKING:
    from light_map.projector import ProjectorDistortionModel


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

    def detect(
        self,
        frame_white: np.ndarray,
        projector_matrix: np.ndarray,
        map_system: MapSystem,
        grid_spacing_svg: float,
        grid_origin_x: float,
        grid_origin_y: float,
        mask_rois: Optional[List[Tuple[int, int, int, int]]],
        distortion_model: Optional["ProjectorDistortionModel"] = None,
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
            map_system,
            grid_spacing_svg,
            grid_origin_x,
            grid_origin_y,
            distortion_model=distortion_model,
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
        map_system,
        grid_spacing_svg,
        grid_origin_x,
        grid_origin_y,
        distortion_model=None,
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
                    distortion_model,
                )
                id_counter = len(tokens) + 1
            else:
                self._process_blob_with_centroid(
                    blob_mask, map_system, tokens, id_counter, distortion_model
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
                    tokens.append(
                        Token(
                            id=id_start + len(tokens),
                            world_x=ox + (gx + 0.5) * spacing,
                            world_y=oy + (gy + 0.5) * spacing,
                            grid_x=gx,
                            grid_y=gy,
                            confidence=1.0,
                        )
                    )
                    found_cells.add((gx, gy))

    def _process_blob_with_centroid(
        self, blob_mask, map_system, tokens, id_counter, distortion_model=None
    ):
        M = cv2.moments(blob_mask)
        if M["m00"] > 0:
            cx, cy = M["m10"] / M["m00"], M["m01"] / M["m00"]
            if distortion_model:
                cx, cy = distortion_model.correct_theoretical_point(cx, cy)
            wx, wy = map_system.screen_to_world(cx, cy)
            tokens.append(
                Token(
                    id=id_counter + len(tokens), world_x=wx, world_y=wy, confidence=1.0
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
