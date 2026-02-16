from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from light_map.map_config import MapConfigManager
    from light_map.map_system import MapSystem
    from .notification import NotificationManager


@dataclass
class AppContext:
    """A shared data container for application state and services."""

    map_system: MapSystem
    map_config_manager: MapConfigManager
    projector_matrix: np.ndarray
    notifications: NotificationManager
