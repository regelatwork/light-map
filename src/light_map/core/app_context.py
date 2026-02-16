from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional

import numpy as np

if TYPE_CHECKING:
    from light_map.map_config import MapConfigManager
    from light_map.map_system import MapSystem
    from .notification import NotificationManager
    from light_map.renderer import Renderer
    from light_map.common_types import AppConfig


@dataclass
class AppContext:
    """A shared data container for application state and services."""

    app_config: AppConfig
    renderer: Renderer
    map_system: MapSystem
    map_config_manager: MapConfigManager
    projector_matrix: np.ndarray
    notifications: NotificationManager
    show_tokens: bool = True
    debug_mode: bool = False
    last_camera_frame: Optional[np.ndarray] = None
