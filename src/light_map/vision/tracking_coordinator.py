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
    from light_map.vision.projection import ProjectionService


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
        projection_service: Optional["ProjectionService"] = None,
    ) -> dict:
        """
        Maps raw ArUco detections (corners, ids) to filtered and snapped Token objects.
        Returns a dict with {"tokens": snapped_list, "raw_tokens": unsnapped_list}.
        """
        map_filename = map_system.svg_loader.filename if map_system.svg_loader else None
        current_time = self.time_provider()

        # 1. Map to raw Token objects
        aruco_detector = getattr(self.token_tracker, "_aruco_detector", None)
        if not aruco_detector:
            return {"tokens": [], "raw_tokens": []}

        token_configs = map_config.get_aruco_configs(map_filename)

        # 1. Resolve unknown IDs before mapping to ensure correct types/heights
        from dataclasses import asdict

        ids = raw_data.get("ids", [])
        if ids is not None:
            for marker_id_entry in ids:
                # Handle both list of ints and numpy array from cv2 (N, 1)
                if isinstance(
                    marker_id_entry,
                    (list, np.ndarray, getattr(np, "ndarray", type(None))),
                ):
                    try:
                        mid = int(marker_id_entry[0])
                    except (TypeError, IndexError):
                        mid = int(marker_id_entry)
                else:
                    mid = int(marker_id_entry)

                if mid not in token_configs:
                    resolved_profile = map_config.resolve_token_profile(
                        mid, map_filename
                    )
                    token_configs[mid] = asdict(resolved_profile)

        raw_detections = aruco_detector.map_to_tokens(
            raw_data,
            map_system,
            token_configs=token_configs,
            ppi=map_config.get_ppi(),
            distortion_model=projector_config.distortion_model,
            projector_3d_model=projector_config.projector_3d_model,
            projection_service=projection_service,
        )

        # 2. Get Grid Parameters
        grid_spacing = 0.0
        grid_origin_x = 0.0
        grid_origin_y = 0.0
        map_bounds = None

        if map_filename:
            map_entry = map_config.data.maps.get(map_filename)
            if map_entry:
                grid_spacing = map_entry.grid_spacing_svg
                grid_origin_x = map_entry.grid_origin_svg_x
                grid_origin_y = map_entry.grid_origin_svg_y

            if map_system.svg_loader and map_system.svg_loader.svg:
                try:
                    svg_doc = map_system.svg_loader.svg
                    if hasattr(svg_doc, "viewbox") and svg_doc.viewbox:
                        viewbox = svg_doc.viewbox
                        map_bounds = (
                            float(viewbox.x),
                            float(viewbox.y),
                            float(viewbox.x + viewbox.width),
                            float(viewbox.y + viewbox.height),
                        )
                    else:
                        map_bounds = (
                            0.0,
                            0.0,
                            float(svg_doc.width),
                            float(svg_doc.height),
                        )
                except (TypeError, ValueError, AttributeError):
                    pass

        # 3. Update filter once (smoothing and occlusion handling)
        # We pass grid_spacing=0 to get smoothed but unsnapped base tokens
        base_filtered_tokens = self.token_filter.update(
            raw_detections,
            current_time,
            grid_spacing=0.0,
            token_configs=token_configs,
            map_bounds=map_bounds,
        )

        # 4. Generate the two versions from the base filtered list
        from dataclasses import replace

        snapped_tokens = []
        raw_tokens_output = []

        for base_token in base_filtered_tokens:
            # The raw version is just the smoothed base
            raw_tokens_output.append(base_token)

            # The snapped version is a copy that we run through snapping
            snapped_token = replace(base_token)
            self.token_filter._apply_grid_snapping(
                snapped_token,
                grid_spacing,
                grid_origin_x,
                grid_origin_y,
                token_configs,
            )
            snapped_tokens.append(snapped_token)

        return {"tokens": snapped_tokens, "raw_tokens": raw_tokens_output}

    def process_aruco_tracking(
        self,
        frame: np.ndarray,
        config: AppConfig,
        map_system: MapSystem,
        map_config: MapConfigManager,
        camera_matrix: Optional[np.ndarray] = None,
        distortion_coefficients: Optional[np.ndarray] = None,
        rotation_vector: Optional[np.ndarray] = None,
        translation_vector: Optional[np.ndarray] = None,
        debug_mode: bool = False,
        projection_service: Optional["ProjectionService"] = None,
    ):
        """Performs background ArUco tracking and updates the map system tokens."""
        if map_config.get_detection_algorithm() != TokenDetectionAlgorithm.ARUCO:
            return

        # Synchronize calibration and debug mode
        self.token_tracker.debug_mode = debug_mode
        if camera_matrix is not None:
            self.token_tracker.set_aruco_calibration(
                camera_matrix=camera_matrix,
                distortion_coefficients=distortion_coefficients,
                rotation_vector=rotation_vector,
                translation_vector=translation_vector,
            )

        # 1. Detect tokens from the frame
        map_filename = map_system.svg_loader.filename if map_system.svg_loader else None
        token_configs = map_config.get_aruco_configs(map_filename)

        # We use the higher-level detect_tokens method to ensure all logic (resizing, masking) is applied.
        # To be proactive, we rely on the fact that detect_tokens will call map_to_tokens,
        # which now handles unknown IDs via token_configs resolution if we provide it.
        # Wait, detect_tokens doesn't take map_filename, so it can't resolve profiles itself.

        # Actually, the best way is to keep the logic that detect_tokens uses but inject the resolution.
        # But for compatibility with tests that mock detect_tokens, we should call it.

        raw_detections = self.token_tracker.detect_tokens(
            frame_white=frame,
            projector_matrix=config.projector_matrix,
            map_system=map_system,
            ppi=map_config.get_ppi(),
            algorithm=TokenDetectionAlgorithm.ARUCO,
            token_configs=token_configs,
            default_height_mm=50.0,  # Default for ArUco tokens
            distortion_model=config.distortion_model,
            projector_3d_model=config.projector_3d_model,
            projection_service=projection_service,
        )

        if raw_detections:
            logging.debug(f"TrackingCoord: Detected {len(raw_detections)} tokens raw.")
            # Ensure all detected IDs are in token_configs for name/color resolution in filtering
            from dataclasses import asdict

            for token in raw_detections:
                if token.id not in token_configs:
                    resolved = map_config.resolve_token_profile(token.id, map_filename)
                    token_configs[token.id] = asdict(resolved)
                    # Also update the token object itself since it was just created with defaults
                    token.name = resolved.name
                    token.type = resolved.type
                    token.color = resolved.color
                    token.size = resolved.size
                    token.height_mm = resolved.height_mm

        # 2. Get Grid Parameters and Filter/Snap
        current_time = self.time_provider()

        grid_spacing = 0.0
        grid_origin_x = 0.0
        grid_origin_y = 0.0
        map_bounds = None

        if map_filename:
            map_entry = map_config.data.maps.get(map_filename)
            if map_entry:
                grid_spacing = map_entry.grid_spacing_svg
                grid_origin_x = map_entry.grid_origin_svg_x
                grid_origin_y = map_entry.grid_origin_svg_y

            # Calculate map bounds from SVG document
            if map_system.svg_loader and map_system.svg_loader.svg:
                try:
                    svg_doc = map_system.svg_loader.svg
                    if hasattr(svg_doc, "viewbox") and svg_doc.viewbox:
                        viewbox = svg_doc.viewbox
                        map_bounds = (
                            float(viewbox.x),
                            float(viewbox.y),
                            float(viewbox.x + viewbox.width),
                            float(viewbox.y + viewbox.height),
                        )
                    else:
                        map_bounds = (
                            0.0,
                            0.0,
                            float(svg_doc.width),
                            float(svg_doc.height),
                        )
                except (TypeError, ValueError, AttributeError):
                    pass

        # Temporal Filtering and Grid Snapping
        filtered_tokens = self.token_filter.update(
            raw_detections,
            current_time,
            grid_spacing=grid_spacing,
            grid_origin_x=grid_origin_x,
            grid_origin_y=grid_origin_y,
            token_configs=token_configs,
            map_bounds=map_bounds,
        )

        # 3. Update map system
        map_system.ghost_tokens = filtered_tokens
