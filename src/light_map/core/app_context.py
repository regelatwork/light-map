from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional, Dict, Any

import numpy as np

from light_map.core.analytics import AnalyticsManager

if TYPE_CHECKING:
    from light_map.map_config import MapConfigManager
    from light_map.map_system import MapSystem
    from .notification import NotificationManager
    from light_map.renderer import Renderer
    from light_map.common_types import AppConfig
    from light_map.projector import ProjectorDistortionModel
    from light_map.vision.aruco_detector import ArucoTokenDetector


@dataclass
class AppContext:
    """A shared data container for application state and services."""

    app_config: AppConfig
    renderer: Renderer
    map_system: MapSystem
    map_config_manager: MapConfigManager
    projector_matrix: np.ndarray
    notifications: NotificationManager
    analytics: AnalyticsManager
    aruco_detector: Optional[ArucoTokenDetector] = None
    camera_matrix: Optional[np.ndarray] = None
    dist_coeffs: Optional[np.ndarray] = None
    camera_rvec: Optional[np.ndarray] = None
    camera_tvec: Optional[np.ndarray] = None
    distortion_model: Optional[ProjectorDistortionModel] = None
    show_tokens: bool = True
    debug_mode: bool = False
    last_camera_frame: Optional[np.ndarray] = None
    raw_aruco: Dict[str, Any] = field(
        default_factory=lambda: {"corners": [], "ids": []}
    )
