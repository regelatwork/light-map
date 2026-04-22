from __future__ import annotations
from typing import Any, Dict, Optional, TYPE_CHECKING
from dataclasses import replace

from light_map.visibility.fow_manager import FogOfWarManager
from light_map.visibility.visibility_engine import VisibilityEngine
from light_map.core.common_types import GridMetadata, SelectionType, SceneId
from light_map.state.world_state import SelectionState

if TYPE_CHECKING:
    from light_map.core.app_context import MainContext
    from light_map.state.world_state import WorldState


class EnvironmentManager:
    def __init__(self, context: MainContext, state: WorldState):
        self.context = context
        self.state = state
        self.visibility_engine = context.visibility_engine
        self.fow_manager: Optional[FogOfWarManager] = None

    def sync_vision(self, state: Optional[WorldState] = None):
        """Forces a line-of-sight visibility sync."""
        state = state or self.state
        map_path = state.map_render_state.filepath

        if (
            self.visibility_engine
            and self.fow_manager
            and map_path
            and state is not None
        ):
            # Calculate latest vision mask on-demand
            combined_pc_mask, disc_ids = (
                self.visibility_engine.get_aggregate_vision_mask(
                    state.tokens,
                    self.context.map_config_manager,
                    self.fow_manager.width,
                    self.fow_manager.height,
                    vision_range_grid=25.0,
                    grid_type=state.grid_type,
                )
            )

            if combined_pc_mask is not None:
                # 1. Update Persistent Fog of War (Explore new areas)
                self.fow_manager.reveal_area(combined_pc_mask, disc_ids)

                # 2. Update Visible Line-of-Sight (the 'clear holes')
                self.fow_manager.set_visible_mask(combined_pc_mask)

                # 3. Save both to stable storage
                self.context.map_config_manager.save_fow_masks(
                    map_path, self.fow_manager
                )

                # 4. Update VisibilityLayer (the highlight)
                state.visibility_mask = combined_pc_mask.copy()

                # 5. Invalidate Layer Caches / Update state
                state.fow_mask = self.fow_manager.explored_mask.copy()
                state.discovered_ids = set(self.fow_manager.discovered_ids)

    def rebuild_visibility_stack(
        self,
        entry: Any,
        current_map_path: str,
        scenes: Optional[Dict[SceneId, Any]] = None,
    ):
        """Re-initializes visibility engine and layers based on map configuration."""
        spacing = entry.grid_spacing_svg if entry.grid_spacing_svg > 0 else 10.0
        origin = (entry.grid_origin_svg_x, entry.grid_origin_svg_y)

        self.visibility_engine = VisibilityEngine(
            grid_spacing_svg=spacing,
            grid_origin=origin,
        )
        self.context.visibility_engine = self.visibility_engine

        # Ensure all scenes and layers that depend on engine are updated
        if scenes and SceneId.EXCLUSIVE_VISION in scenes:
            scenes[SceneId.EXCLUSIVE_VISION].visibility_engine = self.visibility_engine

        if self.context.layer_manager:
            lm = self.context.layer_manager
            lm.visibility_layer.visibility_engine = self.visibility_engine
            lm.exclusive_vision_layer.visibility_engine = self.visibility_engine
            lm.tactical_overlay_layer.visibility_engine = self.visibility_engine
            lm.fow_layer.visibility_engine = self.visibility_engine

        # Sync to WorldState
        self.state.grid_metadata = GridMetadata(
            spacing_svg=spacing,
            origin_svg_x=entry.grid_origin_svg_x,
            origin_svg_y=entry.grid_origin_svg_y,
            type=entry.grid_type,
            overlay_visible=entry.grid_overlay_visible,
            overlay_color=entry.grid_overlay_color,
        )

        # Re-initialize blockers with new visibility engine parameters
        blockers = self.context.map_system.svg_loader.get_visibility_blockers()
        svg_w = self.context.map_system.svg_loader.svg.width
        svg_h = self.context.map_system.svg_loader.svg.height
        mask_w, mask_h = self.visibility_engine.calculate_mask_dimensions(svg_w, svg_h)
        self.visibility_engine.update_blockers(blockers, mask_w, mask_h)

        # Re-initialize Fog of War Manager
        if (
            self.fow_manager is None
            or self.fow_manager.width != mask_w
            or self.fow_manager.height != mask_h
        ):
            self.fow_manager = FogOfWarManager(mask_w, mask_h)
            self.fow_manager.is_disabled = entry.fow_disabled
            if current_map_path:
                self.context.map_config_manager.load_fow_masks(
                    current_map_path, self.fow_manager
                )

        # Sync blockers to state
        self.sync_blockers_to_state()

    def sync_blockers_to_state(self, state: Optional[WorldState] = None):
        """Synchronizes visibility engine blockers to the public state."""
        state = state or self.state
        # Use list() to create a NEW instance, ensuring VersionedAtom detects the change
        blockers = list(self.visibility_engine.blockers)
        state.blockers = blockers

        # Ensure visibility mask is updated to trigger re-render if blockers changed
        if state.visibility_mask is not None:
            state.visibility_mask = state.visibility_mask.copy()

    def toggle_door(self, door_id: str, state: Optional[WorldState] = None):
        """Safely toggles doors and triggers vision sync."""
        state = state or self.state
        if door_id:
            state.selection = SelectionState(type=SelectionType.DOOR, id=door_id)

        if state.selection.type == SelectionType.DOOR and state.selection.id:
            door_id = state.selection.id
            found = False
            for i, blocker in enumerate(self.visibility_engine.blockers):
                if blocker.id == door_id:
                    self.visibility_engine.blockers[i] = replace(
                        blocker, is_open=not blocker.is_open
                    )
                    found = True
            if found:
                self.visibility_engine.update_blockers(
                    self.visibility_engine.blockers,
                    self.fow_manager.width,
                    self.fow_manager.height,
                )
                self.sync_blockers_to_state(state)
                self.context.notifications.add_notification(f"Door {door_id} Toggled")
                if self.context.save_session:
                    self.context.save_session()
                self.sync_vision(state)
        else:
            self.context.notifications.add_notification("No door selected to toggle")

    def reset_fow(self, current_map_path: str, state: Optional[WorldState] = None):
        """Resets the Fog of War for the current map."""
        state = state or self.state
        if self.fow_manager and current_map_path:
            self.fow_manager.reset()
            self.context.map_config_manager.save_fow_masks(
                current_map_path, self.fow_manager
            )
            state.fow_mask = self.fow_manager.explored_mask.copy()
            self.context.notifications.add_notification("Fog of War Reset")

    def toggle_fow(self, current_map_path: str, state: Optional[WorldState] = None):
        """Toggles Fog of War enabled/disabled state."""
        state = state or self.state
        if self.fow_manager:
            self.fow_manager.is_disabled = not self.fow_manager.is_disabled
            state.fow_disabled = self.fow_manager.is_disabled
            if state.fow_mask is not None:
                state.fow_mask = self.fow_manager.explored_mask.copy()

            # Persist to map config
            if current_map_path:
                entry = self.context.map_config_manager.data.maps.get(current_map_path)
                if entry:
                    entry.fow_disabled = self.fow_manager.is_disabled
                    self.context.map_config_manager.save()

            state_str = "OFF" if self.fow_manager.is_disabled else "ON"
            self.context.notifications.add_notification(f"GM: Fog of War {state_str}")
            return self.fow_manager.is_disabled
        return None
