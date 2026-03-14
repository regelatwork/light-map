from __future__ import annotations
from typing import List, TYPE_CHECKING, Any

from light_map.map_layer import MapLayer
from light_map.door_layer import DoorLayer
from light_map.menu_layer import MenuLayer
from light_map.scene_layer import SceneLayer
from light_map.hand_mask_layer import HandMaskLayer
from light_map.overlay_layer import TokenLayer, NotificationLayer, DebugLayer
from light_map.fow_layer import FogOfWarLayer
from light_map.visibility_layer import VisibilityLayer, ExclusiveVisionLayer
from light_map.cursor_layer import CursorLayer

if TYPE_CHECKING:
    from light_map.core.app_context import AppContext
    from light_map.core.world_state import WorldState
    from light_map.common_types import Layer
    from light_map.core.scene import Scene
    from light_map.fow_manager import FogOfWarManager


class LayerStackManager:
    """Manages the creation, configuration, and ordering of rendering layers."""

    def __init__(self, context: AppContext, state: WorldState):
        self.context = context
        self.state = state
        config = context.app_config

        # Core Layers
        self.map_layer = MapLayer(
            state, context.map_system, config.width, config.height
        )
        self.door_layer = DoorLayer(
            state,
            context.visibility_engine,
            config.width,
            config.height,
            thickness_multiplier=config.door_thickness_multiplier,
        )
        self.scene_layer = SceneLayer(
            state, None, config.width, config.height, is_static=False
        )
        self.hand_mask_layer = HandMaskLayer(state, config)
        self.menu_layer = MenuLayer(state)
        self.token_layer = TokenLayer(state, context)
        self.notification_layer = NotificationLayer(state, context)
        self.debug_layer = DebugLayer(state, context)
        self.cursor_layer = CursorLayer(state, context)

        # Visibility and FoW Layers (initialized as placeholders until map loads)
        self.fow_layer = FogOfWarLayer(
            state,
            None,  # No manager yet
            grid_spacing_svg=10.0,
            grid_origin_svg=(0.0, 0.0),
            width=config.width,
            height=config.height,
        )
        self.visibility_layer = VisibilityLayer(
            state,
            config.width,
            config.height,
            grid_spacing_svg=10.0,
            grid_origin_svg=(0.0, 0.0),
            width=config.width,
            height=config.height,
        )
        self.exclusive_vision_layer = ExclusiveVisionLayer(
            state,
            config.width,
            config.height,
            grid_spacing_svg=10.0,
            grid_origin_svg=(0.0, 0.0),
            width=config.width,
            height=config.height,
        )

    @property
    def layer_stack(self) -> List[Layer]:
        """
        Default layer stack ordering (Bottom to Top).
        Used by Scenes that don't override get_active_layers.
        """
        return [
            self.map_layer,
            self.door_layer,
            self.fow_layer,
            self.visibility_layer,
            self.scene_layer,
            self.hand_mask_layer,
            self.token_layer,  # Tokens below Menu
            self.menu_layer,
            self.notification_layer,
            self.debug_layer,
            self.cursor_layer,
        ]

    def update_visibility_stack(
        self,
        fow_manager: FogOfWarManager,
        mask_w: int,
        mask_h: int,
        spacing: float,
        origin: tuple[float, float],
    ):
        """Re-initializes visibility-related layers."""
        config = self.context.app_config

        self.fow_layer = FogOfWarLayer(
            self.state,
            fow_manager,
            spacing,
            origin,
            config.width,
            config.height,
        )
        self.visibility_layer = VisibilityLayer(
            self.state,
            mask_w,
            mask_h,
            spacing,
            origin,
            config.width,
            config.height,
        )
        self.exclusive_vision_layer = ExclusiveVisionLayer(
            self.state,
            mask_w,
            mask_h,
            spacing,
            origin,
            config.width,
            config.height,
        )
        self.door_layer = DoorLayer(
            self.state,
            self.context.visibility_engine,
            config.width,
            config.height,
            thickness_multiplier=config.door_thickness_multiplier,
        )

    def get_stack(self, current_scene: Scene) -> List[Layer]:
        """
        Returns the optimized layer stack for the current scene and state.
        Ensures correct ordering and applies transformations like Exclusive Vision.
        """
        # Get base stack from scene
        # We pass a shim that looks like the app for compatibility with Scene.get_active_layers(app)
        stack = current_scene.get_active_layers(self._get_app_shim())

        # Apply Exclusive Vision transformation if active
        inspected_token_id = self.context.inspected_token_id
        inspected_token_mask = self.context.inspected_token_mask

        if inspected_token_id is not None and inspected_token_mask is not None:
            if self.exclusive_vision_layer:
                self.exclusive_vision_layer.set_mask(inspected_token_mask)

                # Transformation: Insert ExclusiveVisionLayer above Visibility/FoW
                new_stack = []
                for layer in stack:
                    new_stack.append(layer)
                    # After visibility or FoW, insert the exclusive mask
                    if layer == self.visibility_layer or layer == self.fow_layer:
                        if self.exclusive_vision_layer not in new_stack:
                            new_stack.append(self.exclusive_vision_layer)

                # Ensure Exclusive mask is present even if FoW/Visibility were not in stack
                if self.exclusive_vision_layer not in new_stack:
                    # Fallback: insert before UI layers (HandMask, Menu, etc.)
                    try:
                        idx = new_stack.index(self.hand_mask_layer)
                        new_stack.insert(idx, self.exclusive_vision_layer)
                    except ValueError:
                        new_stack.append(self.exclusive_vision_layer)

                return new_stack

        return stack

    def _get_app_shim(self) -> Any:
        """
        Provides a shim object that exposes layer attributes for Scene.get_active_layers.
        This allows us to keep the Scene interface unchanged for now.
        """
        return self

    def update_state(self, state: WorldState):
        """Updates the state for all managed layers."""
        self.state = state
        layers = [
            self.map_layer,
            self.door_layer,
            self.scene_layer,
            self.hand_mask_layer,
            self.menu_layer,
            self.token_layer,
            self.notification_layer,
            self.debug_layer,
            self.cursor_layer,
        ]
        if self.fow_layer:
            layers.append(self.fow_layer)
        if self.visibility_layer:
            layers.append(self.visibility_layer)
        if self.exclusive_vision_layer:
            layers.append(self.exclusive_vision_layer)

        for layer in layers:
            layer.state = state
