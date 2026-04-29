from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np

from light_map.core.analytics import AnalyticsManager
from light_map.state.temporal_event_manager import TemporalEventManager


if TYPE_CHECKING:
    from light_map.core.common_types import AppConfig
    from light_map.core.notification import NotificationManager
    from light_map.map.map_config import MapConfigManager
    from light_map.map.map_system import MapSystem
    from light_map.rendering.projection import CameraProjectionModel, ProjectionService
    from light_map.rendering.renderer import Renderer
    from light_map.state.world_state import WorldState
    from light_map.vision.detectors.aruco_detector import ArucoTokenDetector


@dataclass
class AppContext:
    """A shared data container for application state and services."""

    app_config: AppConfig
    renderer: Renderer
    map_system: MapSystem
    map_config_manager: MapConfigManager
    notifications: NotificationManager
    analytics: AnalyticsManager
    events: TemporalEventManager
    time_provider: Callable[[], float] = time.monotonic
    aruco_detector: ArucoTokenDetector | None = None
    camera_projection_model: CameraProjectionModel | None = None
    projection_service: ProjectionService | None = None
    visibility_engine: Any | None = None  # Avoid circular import
    show_tokens: bool = True
    debug_mode: bool = False
    last_camera_frame: np.ndarray | None = None
    raw_aruco: dict[str, Any] = field(
        default_factory=lambda: {"corners": [], "ids": []}
    )
    raw_tokens: list[Any] = field(default_factory=list)
    state: WorldState | None = None
    layer_manager: Any | None = None  # Avoid circular import
    inspected_token_id: int | None = None
    inspected_token_mask: np.ndarray | None = None
    save_session: Callable[[], None] | None = None


@dataclass
class VisionContext:
    """Stripped-down context for worker processes (e.g., Vision)."""

    app_config: AppConfig
    camera_projection_model: CameraProjectionModel | None = None


@dataclass
class RemoteContext:
    """Minimal context for the API bridge/Remote process."""

    app_config: AppConfig
    state: WorldState | None = None


@dataclass
class MainContext(AppContext):
    """The full context used in the main process."""

    pass
