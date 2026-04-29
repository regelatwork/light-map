import logging
import os
from dataclasses import replace
from typing import TYPE_CHECKING, Any

from light_map.core.common_types import MapRenderState, SessionData, ViewportState
from light_map.map.session_manager import SessionManager
from light_map.rendering.svg.loader import SVGLoader


if TYPE_CHECKING:
    from light_map.interactive_app import InteractiveApp


class PersistenceService:
    """
    Handles all File I/O and configuration persistence for the Interactive App.
    Ensures disk state and WorldState remain synchronized.
    """

    def __init__(self, app: "InteractiveApp"):
        self.app = app
        self.map_config = app.map_config
        self.state = app.state

    def load_map(self, filename: str, load_session: bool = False):
        """Loads an SVG map file and restores its state."""
        filename = os.path.abspath(filename)
        self.app.current_map_path = filename
        self.app.map_system.svg_loader = SVGLoader(filename)

        # Update WorldState for rendering
        self.state.map_render_state = MapRenderState(
            opacity=self.app.layer_manager.map_layer.opacity,
            quality=self.app.layer_manager.map_layer.quality,
            filepath=filename,
        )

        entry = self.map_config.data.maps.get(filename)
        if entry is None:
            from light_map.map.map_config import MapEntry

            self.map_config.data.maps[filename] = MapEntry()
            entry = self.map_config.data.maps[filename]

        # Automatically detect grid spacing if not already set
        if entry.grid_spacing_svg <= 0:
            spacing, ox, oy = self.app.map_system.svg_loader.detect_grid_spacing()
            if spacing > 0:
                logging.info(
                    f"PersistenceService: Auto-detected grid for {filename}: spacing={spacing:.1f}, origin=({ox:.1f}, {oy:.1f})"
                )
                entry.grid_spacing_svg = spacing
                entry.grid_origin_svg_x = ox
                entry.grid_origin_svg_y = oy

                # Calculate initial base scale for this map
                ppi = self.map_config.get_ppi()
                if ppi > 0:
                    entry.scale_factor_1to1 = (
                        entry.physical_unit_inches * ppi
                    ) / spacing
                self.map_config.save()

        # setup Visibility Engine and layers (Delegated to app for now)
        self.app._rebuild_visibility_stack(entry)
        self.state.fow_disabled = entry.fow_disabled

        # Restore persistent states
        if self.app.fow_manager:
            self.state.visibility_mask = self.app.fow_manager.visible_mask.copy()
            self.state.fow_mask = self.app.fow_manager.explored_mask.copy()
            self.state.discovered_ids = set(self.app.fow_manager.discovered_ids)

        # Calculate and set base scale (1:1 zoom level)
        self.app.refresh_base_scale()

        if load_session:
            session_dir = None
            if self.app.config.storage_manager:
                session_dir = os.path.join(
                    self.app.config.storage_manager.get_data_dir(), "sessions"
                )
            session = SessionManager.load_for_map(filename, session_dir=session_dir)
            if session:
                self.app.map_system.ghost_tokens = session.tokens
                self.state.tokens = list(session.tokens)

                from light_map.visibility.visibility_types import VisibilityType

                # Restore door states
                for blocker in self.app.visibility_engine.blockers:
                    if (
                        blocker.type == VisibilityType.DOOR
                        and blocker.id in session.door_states
                    ):
                        blocker.is_open = session.door_states[blocker.id]

                self.app.visibility_engine.update_blockers(
                    self.app.visibility_engine.blockers,
                    self.app.fow_manager.width,
                    self.app.fow_manager.height,
                )
                # Sync state.blockers so frontend gets updated is_open status
                self.app._sync_blockers_to_state()

                if session.viewport:
                    self.app.map_system.set_state(
                        session.viewport.x,
                        session.viewport.y,
                        session.viewport.zoom,
                        session.viewport.rotation,
                    )
                self.map_config.data.global_settings.last_used_map = filename
                self.map_config.save()
                self.app.switch_to_viewing()
                return

        # Default loading if no session or session load failed
        vp = self.map_config.get_map_viewport(filename)
        self.app.map_system.set_state(vp.x, vp.y, vp.zoom, vp.rotation)

        self.map_config.data.global_settings.last_used_map = filename
        self.map_config.save()

        # Switch to Viewing Scene to ensure map is visible
        self.app.switch_to_viewing()

    def save_session(self):
        """Saves the current session (tokens and viewport)."""
        if not self.app.map_system.is_map_loaded():
            return

        map_file = self.app.map_system.svg_loader.filename
        session_dir = None
        if self.app.config.storage_manager:
            session_dir = os.path.join(
                self.app.config.storage_manager.get_data_dir(), "sessions"
            )

        from light_map.visibility.visibility_types import VisibilityType

        # Collect current door states
        door_states = {
            b.id: b.is_open
            for b in self.app.visibility_engine.blockers
            if b.type == VisibilityType.DOOR
        }

        session = SessionData(
            map_file=map_file,
            viewport=ViewportState(
                x=self.app.map_system.state.x,
                y=self.app.map_system.state.y,
                zoom=self.app.map_system.state.zoom,
                rotation=self.app.map_system.state.rotation,
            ),
            tokens=self.app.map_system.ghost_tokens,
            door_states=door_states,
        )
        SessionManager.save_for_map(map_file, session, session_dir=session_dir)

    def update_token(self, token_id: int, **kwargs):
        """Updates a token definition or override."""
        # Try to get existing definition to preserve fields
        existing_def = None
        is_map_override = kwargs.get("is_map_override", False)

        map_file = self.app.current_map_path
        if map_file:
            map_entry = self.map_config.data.maps.get(map_file)
            if map_entry:
                existing_def = map_entry.aruco_overrides.get(token_id)
                if existing_def:
                    # If it was already an override, keep it that way unless explicitly told otherwise
                    if "is_map_override" not in kwargs:
                        is_map_override = True

        if not existing_def:
            existing_def = self.map_config.data.global_settings.aruco_defaults.get(
                token_id
            )

        # Use existing values if not provided in the update
        final_name = kwargs.get("name")
        if final_name is None:
            final_name = existing_def.name if existing_def else f"Token {token_id}"

        final_type = kwargs.get("type")
        if final_type is None:
            final_type = existing_def.type if existing_def else "NPC"

        final_profile = kwargs.get("profile")
        final_size = kwargs.get("size")
        final_height_mm = kwargs.get("height_mm")

        if final_profile is not None:
            if final_profile == "":
                final_profile = None
            else:
                final_size = None
                final_height_mm = None
        elif final_size is not None or final_height_mm is not None:
            final_profile = None
        else:
            if existing_def:
                final_profile = existing_def.profile
                final_size = existing_def.size
                final_height_mm = existing_def.height_mm

        final_color = kwargs.get("color")
        if final_color is None:
            final_color = existing_def.color if existing_def else None

        if is_map_override and map_file:
            self.map_config.set_map_aruco_override(
                map_name=map_file,
                aruco_id=token_id,
                name=final_name,
                type=final_type,
                profile=final_profile,
                size=final_size,
                height_mm=final_height_mm,
                color=final_color,
            )
            logging.info(
                f"PersistenceService: Updated MAP override for token {token_id} on {os.path.basename(map_file)}"
            )
        else:
            self.map_config.set_global_aruco_definition(
                aruco_id=token_id,
                name=final_name,
                type=final_type,
                profile=final_profile,
                size=final_size,
                height_mm=final_height_mm,
                color=final_color,
            )
            logging.info(
                f"PersistenceService: Updated GLOBAL definition for token {token_id}"
            )

        # Trigger WorldState update for tokens to reflect config changes
        # This assumes WorldState.tokens will be refreshed by the main loop or here.
        # Force a config version increment in WorldState
        self.state.config_data += 1

    def update_grid(self, map_path: str, **kwargs):
        """Updates grid configuration for a map."""
        map_path = os.path.abspath(map_path)
        entry = self.map_config.data.maps.get(map_path)
        if entry:
            if "offset_x" in kwargs:
                entry.grid_origin_svg_x = kwargs["offset_x"]
            if "offset_y" in kwargs:
                entry.grid_origin_svg_y = kwargs["offset_y"]

            spacing = kwargs.get("spacing")
            if spacing is not None and spacing > 0:
                entry.grid_spacing_svg = spacing
                # Base scale depends on grid spacing
                self.app.refresh_base_scale()

            grid_type_val = kwargs.get("grid_type")
            if grid_type_val:
                from light_map.core.common_types import GridType

                try:
                    entry.grid_type = GridType(grid_type_val)
                except ValueError:
                    logging.warning(
                        f"PersistenceService: Invalid grid type {grid_type_val}"
                    )

            visible = kwargs.get("visible")
            if visible is not None:
                entry.grid_overlay_visible = bool(visible)

            color = kwargs.get("color")
            if color:
                entry.grid_overlay_color = color

            self.map_config.save()

            # Sync to current state if this is the active map
            if self.app.current_map_path == map_path:
                from light_map.core.common_types import GridMetadata

                self.state.grid_metadata = GridMetadata(
                    spacing_svg=entry.grid_spacing_svg,
                    origin_svg_x=entry.grid_origin_svg_x,
                    origin_svg_y=entry.grid_origin_svg_y,
                    type=entry.grid_type,
                    overlay_visible=entry.grid_overlay_visible,
                    overlay_color=entry.grid_overlay_color,
                )
                if self.app.environment_manager:
                    self.app.environment_manager.rebuild_visibility_stack(
                        entry, map_path
                    )

            self.state.config_data += 1

    def toggle_grid(self, map_path: str):
        """Toggles the grid visibility for a map."""
        map_path = os.path.abspath(map_path)
        entry = self.map_config.data.maps.get(map_path)
        if entry:
            entry.grid_overlay_visible = not entry.grid_overlay_visible
            self.map_config.save()

            if self.app.current_map_path == map_path:
                self.state.grid_metadata = replace(
                    self.state.grid_metadata, overlay_visible=entry.grid_overlay_visible
                )
            self.state.config_data += 1
            return entry.grid_overlay_visible
        return None

    def set_grid_color(self, map_path: str, color: str):
        """Sets the grid color for a map."""
        map_path = os.path.abspath(map_path)
        entry = self.map_config.data.maps.get(map_path)
        if entry:
            entry.grid_overlay_color = color
            self.map_config.save()

            if self.app.current_map_path == map_path:
                self.state.grid_metadata = replace(
                    self.state.grid_metadata, overlay_color=color
                )
            self.state.config_data += 1

    def delete_token_override(self, token_id: int):
        """Deletes a map-specific token override."""
        map_file = self.app.current_map_path
        if token_id is not None and map_file:
            self.map_config.delete_map_aruco_override(map_file, token_id)
            logging.info(
                f"PersistenceService: Deleted MAP override for token {token_id}"
            )
            self.state.config_data += 1

    def delete_token(self, token_id: int):
        """Deletes a global token definition."""
        if token_id is not None:
            self.map_config.delete_global_aruco_definition(token_id)
            logging.info(
                f"PersistenceService: Deleted GLOBAL definition for token {token_id}"
            )
            self.state.config_data += 1

    def update_token_profile(self, name: str, size: float, height_mm: float):
        """Updates or creates a token profile."""
        if name is not None and size is not None and height_mm is not None:
            self.map_config.set_token_profile(name, size, height_mm)
            logging.info(f"PersistenceService: Updated profile '{name}'")
            self.state.config_data += 1

    def delete_token_profile(self, name: str):
        """Deletes a token profile."""
        if name is not None:
            self.map_config.delete_token_profile(name)
            logging.info(f"PersistenceService: Deleted profile '{name}'")
            self.state.config_data += 1

    def update_system_config(self, payload: dict[str, Any]):
        """Updates global system configuration."""
        from light_map.core.config_schema import GlobalConfigSchema
        from light_map.core.config_utils import sync_pydantic_to_dataclass

        try:
            validated = GlobalConfigSchema(**payload)
            self.map_config.update_global_settings(payload)
            sync_pydantic_to_dataclass(validated, self.app.config)

            # Handle side effects
            if "projector_ppi" in payload:
                self.app.refresh_base_scale()

            self.state.config_data += 1
            return True
        except Exception as e:
            logging.error(f"PersistenceService: Failed to update config: {e}")
            return False

    def toggle_hand_masking(self):
        """Toggles hand masking in global settings."""
        gs = self.map_config.data.global_settings
        gs.enable_hand_masking = not gs.enable_hand_masking
        self.map_config.save()
        self.app.config.enable_hand_masking = gs.enable_hand_masking
        self.state.config_data += 1
        return gs.enable_hand_masking

    def set_gm_position(self, position: str):
        """Sets the GM position in global settings."""
        from light_map.core.common_types import GmPosition

        try:
            new_pos = GmPosition(position)
            gs = self.map_config.data.global_settings
            gs.gm_position = new_pos
            self.map_config.save()
            self.app.config.gm_position = gs.gm_position
            self.state.config_data += 1
            return new_pos
        except (ValueError, KeyError):
            return None
