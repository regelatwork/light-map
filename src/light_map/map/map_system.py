import logging
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import svgelements

from light_map.core.common_types import AppConfig, Token
from light_map.rendering.svg import SVGLoader


if TYPE_CHECKING:
    from light_map.core.common_types import ViewportState


@dataclass
class MapState:
    x: float = 0.0
    y: float = 0.0
    zoom: float = 1.0
    rotation: float = 0.0  # Degrees

    def to_viewport(self) -> "ViewportState":
        from light_map.core.common_types import ViewportState

        return ViewportState(x=self.x, y=self.y, zoom=self.zoom, rotation=self.rotation)


class MapSystem:
    def __init__(self, config: "AppConfig"):
        self.config = config
        self.state = MapState()
        self.svg_loader: SVGLoader | None = None
        self.base_scale: float = 1.0
        self.ghost_tokens: list[Token] = []
        self._cached_matrix: svgelements.Matrix | None = None
        self._cached_state_tuple: tuple[float, float, float, float] | None = None

        # Undo/Redo stacks
        self.undo_stack: list[MapState] = []
        self.redo_stack: list[MapState] = []
        self.max_stack_size = 50

    @property
    def width(self) -> int:
        return self.config.width

    @property
    def height(self) -> int:
        return self.config.height

    def is_map_loaded(self) -> bool:
        """Returns True if an SVG map is currently loaded."""
        return self.svg_loader is not None

    def push_state(self):
        """Pushes current state to undo stack and clears redo stack."""
        from copy import deepcopy

        self.undo_stack.append(deepcopy(self.state))
        if len(self.undo_stack) > self.max_stack_size:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self):
        """Reverts to the last saved state."""
        if not self.undo_stack:
            return
        from copy import deepcopy

        self.redo_stack.append(deepcopy(self.state))
        self.state = self.undo_stack.pop()

    def redo(self):
        """Restores the state that was undone."""
        if not self.redo_stack:
            return
        from copy import deepcopy

        self.undo_stack.append(deepcopy(self.state))
        self.state = self.redo_stack.pop()

    def can_undo(self) -> bool:
        return len(self.undo_stack) > 0

    def can_redo(self) -> bool:
        return len(self.redo_stack) > 0

    def set_state(self, x: float, y: float, zoom: float, rotation: float):
        self.state.x = x
        self.state.y = y
        self.state.zoom = zoom
        self.state.rotation = rotation

    def pan(self, dx: float, dy: float):
        self.state.x += dx
        self.state.y += dy

    def zoom(
        self,
        factor: float,
        center_x: float | None = None,
        center_y: float | None = None,
    ):
        """
        Adjust zoom level relative to a screen point.
        """
        if center_x is None:
            center_x = self.width / 2
        if center_y is None:
            center_y = self.height / 2

        # Get world coordinate of center BEFORE zoom
        wx, wy = self.screen_to_world(center_x, center_y)

        new_zoom = self.state.zoom * factor

        # Use robust pivot logic
        self.set_zoom_around_pivot(new_zoom, center_x, center_y, wx, wy)

    def set_zoom_around_pivot(
        self, new_zoom: float, sx: float, sy: float, wx: float, wy: float
    ):
        """
        Sets the zoom level and adjusts pan (x, y) so that the given world coordinate (wx, wy)
        maps to the given screen coordinate (sx, sy).
        """
        if new_zoom <= 0:
            new_zoom = 0.001
        self.state.zoom = new_zoom

        cx, cy = self.width / 2, self.height / 2

        # Construct transform part without Translation (T)
        # matches SVGLoader logic: Scale -> Rotate(around center) -> Translate
        m_no_t = svgelements.Matrix()
        m_no_t.post_scale(new_zoom, new_zoom)
        m_no_t.post_rotate(math.radians(self.state.rotation), cx, cy)

        # Transform World Point
        p_transformed = m_no_t.point_in_matrix_space((wx, wy))

        # Calculate required Translation
        # S = P_transformed + T  =>  T = S - P_transformed
        self.state.x = sx - p_transformed.x
        self.state.y = sy - p_transformed.y

    def rotate(self, degrees: float):
        """Rotate map in 90 degree increments."""
        # Ensure we stay in 0, 90, 180, 270
        self.state.rotation = (self.state.rotation + degrees) % 360

    def reset_view(self):
        self.state = MapState(zoom=self.base_scale)

    def reset_zoom_to_base(self):
        """Resets the zoom to the current map's base 1:1 scale, pivoting around screen center."""
        cx, cy = self.width / 2, self.height / 2
        # Get world coordinate currently at center
        wx, wy = self.screen_to_world(cx, cy)

        # Apply new zoom while keeping (wx, wy) at (cx, cy)
        self.set_zoom_around_pivot(self.base_scale, cx, cy, wx, wy)

    def reset_view_to_base(self):
        """Resets the view to the default state but using the base scale."""
        self.state = MapState(zoom=self.base_scale)

    def zoom_pinned(self, factor: float, center_point: tuple[int, int]):
        """Adjusts zoom relative to a fixed screen point."""
        center_x, center_y = center_point
        wx, wy = self.screen_to_world(center_x, center_y)
        new_zoom = self.state.zoom * factor
        self.set_zoom_around_pivot(new_zoom, center_x, center_y, wx, wy)

    def get_render_params(self) -> dict[str, Any]:
        """Returns parameters for SVGLoader.render()."""
        return {
            "scale_factor": self.state.zoom,
            "offset_x": int(self.state.x),
            "offset_y": int(self.state.y),
            "rotation": self.state.rotation,
        }

    def _get_matrix(self) -> svgelements.Matrix:
        """Reconstructs the full transformation matrix used by SVGLoader."""
        current_state = (
            self.state.x,
            self.state.y,
            self.state.zoom,
            self.state.rotation,
        )
        if (
            self._cached_matrix is not None
            and self._cached_state_tuple == current_state
        ):
            return self._cached_matrix

        cx, cy = self.width / 2, self.height / 2
        m = svgelements.Matrix()
        m.post_scale(self.state.zoom, self.state.zoom)
        m.post_rotate(math.radians(self.state.rotation), cx, cy)
        m.post_translate(self.state.x, self.state.y)

        self._cached_matrix = m
        self._cached_state_tuple = current_state
        return m

    def screen_to_world(self, sx: float, sy: float) -> tuple[float, float]:
        """Converts screen coordinates to world (map) coordinates."""
        m = self._get_matrix()
        # Invert matrix to go Screen -> World
        im = ~m
        p = im.point_in_matrix_space((sx, sy))
        return p.x, p.y

    def world_to_screen(self, wx: float, wy: float) -> tuple[float, float]:
        """Converts world coordinates to screen coordinates."""
        m = self._get_matrix()
        p = m.point_in_matrix_space((wx, wy))
        logging.debug(
            f"MapSystem: world {wx:.1f},{wy:.1f} -> screen {p.x:.1f},{p.y:.1f}"
        )
        return p.x, p.y

    def world_mm_to_svg(
        self, wx_mm: float, wy_mm: float, ppi: float | None = None
    ) -> tuple[float, float]:
        """
        Converts physical world coordinates (mm) to map (SVG) coordinates.
        This assumes the projector's PPI and that origin (0,0) in mm
        maps to (0,0) in projector pixels.
        """
        if ppi is None:
            ppi = getattr(self.config, "projector_ppi", 55.0)
        ppi_mm = ppi / 25.4
        sx = wx_mm * ppi_mm
        sy = wy_mm * ppi_mm
        return self.screen_to_world(sx, sy)
