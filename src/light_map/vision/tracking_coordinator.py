from __future__ import annotations
import numpy as np
import logging
from typing import TYPE_CHECKING, Optional

from light_map.common_types import TokenDetectionAlgorithm
from light_map.vision.token_filter import TokenFilter
from light_map.token_tracker import TokenTracker

if TYPE_CHECKING:
    from light_map.map_system import MapSystem
    from light_map.map_config import MapConfigManager
    from light_map.common_types import AppConfig


class TrackingCoordinator:
    """Coordinates background token tracking and temporal filtering."""

    def __init__(self, time_provider):
        self.time_provider = time_provider
        self.token_tracker = TokenTracker()
        self.token_filter = TokenFilter()

    def map_and_filter_aruco(
        self,
        raw_data: dict,
        map_system: MapSystem,
        map_config: MapConfigManager,
        projector_config: AppConfig,
    ) -> dict:
        """
        Maps raw ArUco detections (corners, ids) to filtered and snapped Token objects.
        Returns a dict with {"tokens": snapped_list, "raw_tokens": unsnapped_list}.
        """
        map_file = map_system.svg_loader.filename if map_system.svg_loader else None
        current_time = self.time_provider()

        # 1. Map to raw Token objects
        detector = getattr(self.token_tracker, "_aruco_detector", None)
        if not detector:
            return {"tokens": [], "raw_tokens": []}

        token_configs = map_config.get_aruco_configs(map_file)
        detections = detector.map_to_tokens(
            raw_data,
            map_system,
            token_configs=token_configs,
            ppi=map_config.get_ppi(),
            distortion_model=projector_config.distortion_model,
        )

        # 2. Get Grid Parameters
        grid_spacing = 0.0
        grid_origin_x = 0.0
        grid_origin_y = 0.0
        map_bounds = None

        if map_file:
            entry = map_config.data.maps.get(map_file)
            if entry:
                grid_spacing = entry.grid_spacing_svg
                grid_origin_x = entry.grid_origin_svg_x
                grid_origin_y = entry.grid_origin_svg_y

            if map_system.svg_loader and map_system.svg_loader.svg:
                try:
                    svg = map_system.svg_loader.svg
                    if hasattr(svg, "viewbox") and svg.viewbox:
                        vb = svg.viewbox
                        map_bounds = (
                            float(vb.x),
                            float(vb.y),
                            float(vb.x + vb.width),
                            float(vb.y + vb.height),
                        )
                    else:
                        map_bounds = (0.0, 0.0, float(svg.width), float(svg.height))
                except (TypeError, ValueError, AttributeError):
                    pass

        # 3. Update filter once (smoothing and occlusion handling)
        # We pass grid_spacing=0 to get smoothed but unsnapped base tokens
        base_filtered_tokens = self.token_filter.update(
            detections,
            current_time,
            grid_spacing=0.0,
            token_configs=token_configs,
            map_bounds=map_bounds,
        )

        # 4. Generate the two versions from the base filtered list
        from dataclasses import replace

        snapped_tokens = []
        raw_tokens = []

        for bt in base_filtered_tokens:
            # The raw version is just the smoothed base
            raw_tokens.append(bt)

            # The snapped version is a copy that we run through snapping
            snapped_t = replace(bt)
            self.token_filter._apply_grid_snapping(
                snapped_t,
                grid_spacing,
                grid_origin_x,
                grid_origin_y,
                token_configs,
            )
            snapped_tokens.append(snapped_t)

        return {"tokens": snapped_tokens, "raw_tokens": raw_tokens}

    def process_aruco_tracking(
        self,
        frame: np.ndarray,
        config: AppConfig,
        map_system: MapSystem,
        map_config: MapConfigManager,
        camera_matrix: Optional[np.ndarray] = None,
        dist_coeffs: Optional[np.ndarray] = None,
        rvec: Optional[np.ndarray] = None,
        tvec: Optional[np.ndarray] = None,
        debug_mode: bool = False,
    ):
        """Performs background ArUco tracking and updates the map system tokens."""
        if map_config.get_detection_algorithm() != TokenDetectionAlgorithm.ARUCO:
            return

        # Synchronize calibration and debug mode
        self.token_tracker.debug_mode = debug_mode
        if camera_matrix is not None:
            self.token_tracker.set_aruco_calibration(
                camera_matrix=camera_matrix,
                dist_coeffs=dist_coeffs,
                rvec=rvec,
                tvec=tvec,
            )

        # 1. Detect tokens from the frame
        token_configs = map_config.get_aruco_configs(
            map_system.svg_loader.filename if map_system.svg_loader else None
        )

        detections = self.token_tracker.detect_tokens(
            frame_white=frame,
            projector_matrix=config.projector_matrix,
            map_system=map_system,
            ppi=map_config.get_ppi(),
            algorithm=TokenDetectionAlgorithm.ARUCO,
            token_configs=token_configs,
            default_height_mm=5.0,  # Default for ArUco tokens
            distortion_model=config.distortion_model,
        )

        if detections:
            logging.debug(f"TrackingCoord: Detected {len(detections)} tokens raw.")

        # 2. Get Grid Parameters and Filter/Snap
        map_file = map_system.svg_loader.filename if map_system.svg_loader else None
        current_time = self.time_provider()

        grid_spacing = 0.0
        grid_origin_x = 0.0
        grid_origin_y = 0.0
        map_bounds = None

        if map_file:
            entry = map_config.data.maps.get(map_file)
            if entry:
                grid_spacing = entry.grid_spacing_svg
                grid_origin_x = entry.grid_origin_svg_x
                grid_origin_y = entry.grid_origin_svg_y

            # Calculate map bounds from SVG document
            if map_system.svg_loader and map_system.svg_loader.svg:
                try:
                    svg = map_system.svg_loader.svg
                    if hasattr(svg, "viewbox") and svg.viewbox:
                        vb = svg.viewbox
                        map_bounds = (
                            float(vb.x),
                            float(vb.y),
                            float(vb.x + vb.width),
                            float(vb.y + vb.height),
                        )
                    else:
                        map_bounds = (0.0, 0.0, float(svg.width), float(svg.height))
                except (TypeError, ValueError, AttributeError):
                    pass

        # Temporal Filtering and Grid Snapping
        tokens = self.token_filter.update(
            detections,
            current_time,
            grid_spacing=grid_spacing,
            grid_origin_x=grid_origin_x,
            grid_origin_y=grid_origin_y,
            token_configs=token_configs,
            map_bounds=map_bounds,
        )

        # 3. Update map system
        map_system.ghost_tokens = tokens
