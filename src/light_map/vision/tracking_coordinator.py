from __future__ import annotations
import numpy as np
from typing import TYPE_CHECKING

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
    ):
        """Performs background ArUco tracking and updates the map system tokens."""
        if map_config.get_detection_algorithm() != TokenDetectionAlgorithm.ARUCO:
            return

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
            distortion_model=config.distortion_model,
        )

        # Grid parameters
        grid_spacing = 0.0
        grid_origin_x = 0.0
        grid_origin_y = 0.0
        if map_file:
            entry = map_config.data.maps.get(map_file)
            if entry:
                grid_spacing = entry.grid_spacing_svg
                grid_origin_x = entry.grid_origin_svg_x
                grid_origin_y = entry.grid_origin_svg_y

        # Temporal Filtering and Grid Snapping
        tokens = self.token_filter.update(
            detections,
            current_time,
            grid_spacing=grid_spacing,
            grid_origin_x=grid_origin_x,
            grid_origin_y=grid_origin_y,
            token_configs=token_configs,
        )

        # Update map system
        map_system.ghost_tokens = tokens
