from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional, Dict, Any, List, Callable

import numpy as np

from light_map.core.analytics import AnalyticsManager
from light_map.core.temporal_event_manager import TemporalEventManager

if TYPE_CHECKING:
    from .world_state import WorldState
    from light_map.map_config import MapConfigManager
    from light_map.map_system import MapSystem
    from .notification import NotificationManager
    from light_map.renderer import Renderer
    from light_map.common_types import AppConfig
    from light_map.projector import ProjectorDistortionModel
    from light_map.vision.aruco_detector import ArucoTokenDetector
    from light_map.vision.projection import CameraProjectionModel


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
    events: TemporalEventManager
    aruco_detector: Optional[ArucoTokenDetector] = None
    camera_projection_model: Optional[CameraProjectionModel] = None
    camera_matrix: Optional[np.ndarray] = None
    distortion_coefficients: Optional[np.ndarray] = None
    camera_rotation_vector: Optional[np.ndarray] = None
    camera_translation_vector: Optional[np.ndarray] = None
    distortion_model: Optional[ProjectorDistortionModel] = None
    visibility_engine: Optional[Any] = None  # Avoid circular import
    show_tokens: bool = True
    debug_mode: bool = False
    last_camera_frame: Optional[np.ndarray] = None
    raw_aruco: Dict[str, Any] = field(
        default_factory=lambda: {"corners": [], "ids": []}
    )
    raw_tokens: List[Any] = field(default_factory=list)
    state: Optional[WorldState] = None
    inspected_token_id: Optional[int] = None
    inspected_token_mask: Optional[np.ndarray] = None
    save_session: Optional[Callable[[], None]] = None
