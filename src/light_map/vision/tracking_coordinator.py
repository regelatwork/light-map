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

        # We also need extrinsics. For now, let ArucoDetector load from disk if not set,
        # but ideally we should pass it.
        # Actually, let's load it here if needed or trust the detector.
        # But wait! ArucoDetector loads them in __init__.
        # If we want to support dynamic updates, we should pass them.

        map_file = map_system.svg_loader.filename if map_system.svg_loader else None
        current_time = self.time_provider()

        # Get resolved configs for current map
        token_configs = map_config.get_aruco_configs(map_file)

        # Detect
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
            for d in detections:
                logging.debug(f"  ID {d.id}: world=({d.world_x:.1f}, {d.world_y:.1f})")

        # Grid parameters
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
                    # Prefer viewbox if available as it defines the active coordinate range
                    if hasattr(svg, "viewbox") and svg.viewbox:
                        vb = svg.viewbox
                        map_bounds = (
                            float(vb.x),
                            float(vb.y),
                            float(vb.x + vb.width),
                            float(vb.y + vb.height),
                        )
                    else:
                        # Fallback to width/height starting from origin
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

        if tokens:
            logging.debug(f"TrackingCoord: Filtered {len(tokens)} tokens.")
            for t in tokens:
                logging.debug(
                    f"  ID {t.id}: world=({t.world_x:.1f}, {t.world_y:.1f}) snap=({t.grid_x}, {t.grid_y})"
                )

        # Update map system
        map_system.ghost_tokens = tokens
