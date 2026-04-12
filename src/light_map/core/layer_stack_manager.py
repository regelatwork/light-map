from __future__ import annotations
from typing import List, TYPE_CHECKING, Any

from light_map.rendering.layers.map_layer import MapLayer
from light_map.rendering.layers.door_layer import DoorLayer
from light_map.rendering.layers.menu_layer import MenuLayer
from light_map.rendering.layers.hand_mask_layer import HandMaskLayer
from light_map.rendering.layers.aruco_mask_layer import ArucoMaskLayer
from light_map.rendering.layers.overlay_layer import (
    TokenLayer,
    NotificationLayer,
    DebugLayer,
)
from light_map.rendering.layers.fow_layer import FogOfWarLayer
from light_map.rendering.layers.visibility_layer import (
    VisibilityLayer,
    ExclusiveVisionLayer,
)
from light_map.rendering.layers.cursor_layer import CursorLayer
from light_map.rendering.layers.selection_progress_layer import SelectionProgressLayer
from light_map.rendering.layers.flash_layer import FlashLayer
from light_map.rendering.layers.map_grid_layer import MapGridLayer
from light_map.rendering.layers.calibration_layer import CalibrationLayer
from light_map.core.common_types import Layer, CompositeLayer

if TYPE_CHECKING:
    from light_map.core.app_context import AppContext
    from light_map.state.world_state import WorldState
    from light_map.core.scene import Scene
    from light_map.visibility.fow_manager import FogOfWarManager


class LayerStackManager:
    """Manages the creation, configuration, and ordering of rendering layers."""

    def __init__(self, context: AppContext, state: WorldState):
        self.context = context
        self.state = state
        self.config = context.app_config
        config = self.config

        # Core Layers
        self.map_layer = MapLayer(
            state, context.map_system, config.width, config.height
        )
        self.door_layer = DoorLayer(
            state,
            config.width,
            config.height,
            thickness_multiplier=config.door_thickness_multiplier,
        )
        self.hand_mask_layer = HandMaskLayer(
            state, config, projection_service=context.projection_service
        )
        self.aruco_mask_layer = ArucoMaskLayer(
            state, config, projection_service=context.projection_service
        )
        self.menu_layer = MenuLayer(state)
        self.token_layer = TokenLayer(state, context)
        self.notification_layer = NotificationLayer(state, context)
        self.debug_layer = DebugLayer(state, context)
        self.selection_progress_layer = SelectionProgressLayer(state, context)
        self.cursor_layer = CursorLayer(state, context)

        # Calibration-related Layers
        self.flash_layer = FlashLayer(state, config.width, config.height)
        self.map_grid_layer = MapGridLayer(state, config.width, config.height)
        self.calibration_layer = CalibrationLayer(state, self.config)

        # Visibility and FoW Layers
        self.fow_layer = FogOfWarLayer(state, config.width, config.height)
        self.visibility_layer = VisibilityLayer(state, config.width, config.height)
        self.exclusive_vision_layer = ExclusiveVisionLayer(
            state, config.width, config.height
        )

        # Background Composite (Optimized for performance)
        self.background_composite = CompositeLayer(
            [self.map_layer, self.door_layer, self.fow_layer, self.visibility_layer]
        )

    @property
    def layer_stack(self) -> List[Layer]:
        """
        Default layer stack ordering (Bottom to Top).
        Used by Scenes that don't override get_active_layers.
        """
        return [
            self.background_composite,
            self.hand_mask_layer,
            self.token_layer,
            self.menu_layer,
            self.notification_layer,
            self.debug_layer,
            self.selection_progress_layer,
            self.cursor_layer,
            self.aruco_mask_layer,  # TOPMOST
        ]

    def update_visibility_stack(
        self,
        fow_manager: FogOfWarManager,
        mask_w: int,
        mask_h: int,
        spacing: float,
        origin: tuple[float, float],
    ):
        """
        No-op. Layers are now reactive and pull data from WorldState atoms.
        This method is kept for compatibility with current InteractiveApp calls.
        """
        pass

    def get_stack(self, current_scene: Scene) -> List[Layer]:
        """
        Returns the optimized layer stack for the current scene and state.
        Ensures correct ordering and applies transformations.
        """
        # Get base stack from scene
        # We pass a shim that looks like the app for compatibility with Scene.get_active_layers(app)
        return current_scene.get_active_layers(self._get_app_shim())

    def _get_app_shim(self) -> Any:
        """
        Provides a shim object that exposes layer attributes for Scene.get_active_layers.
        This allows us to keep the Scene interface unchanged for now.
        """
        return self

    def update_state(self, state: WorldState):
        """Updates the state for all managed layers."""
        self.state = state
        self.background_composite.state = state
        layers = [
            self.map_layer,
            self.door_layer,
            self.aruco_mask_layer,
            self.hand_mask_layer,
            self.menu_layer,
            self.token_layer,
            self.notification_layer,
            self.debug_layer,
            self.selection_progress_layer,
            self.cursor_layer,
            self.flash_layer,
            self.map_grid_layer,
            self.calibration_layer,
        ]
        if self.fow_layer:
            layers.append(self.fow_layer)
        if self.visibility_layer:
            layers.append(self.visibility_layer)
        if self.exclusive_vision_layer:
            layers.append(self.exclusive_vision_layer)

        for layer in layers:
            layer.state = state
