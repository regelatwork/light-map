from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple
import svgelements
import math


@dataclass
class MapState:
    x: float = 0.0
    y: float = 0.0
    zoom: float = 1.0
    rotation: float = 0.0  # Degrees


class MapSystem:
    def __init__(self, screen_width: int, screen_height: int):
        self.width = screen_width
        self.height = screen_height
        self.state = MapState()

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
        center_x: Optional[float] = None,
        center_y: Optional[float] = None,
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

    def set_zoom_around_pivot(self, new_zoom: float, sx: float, sy: float, wx: float, wy: float):
        """
        Sets the zoom level and adjusts pan (x, y) so that the given world coordinate (wx, wy)
        maps to the given screen coordinate (sx, sy).
        """
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
        self.state = MapState()

    def get_render_params(self) -> Dict[str, Any]:
        """Returns parameters for SVGLoader.render()."""
        return {
            "scale_factor": self.state.zoom,
            "offset_x": int(self.state.x),
            "offset_y": int(self.state.y),
            "rotation": self.state.rotation,
        }

    def _get_matrix(self) -> svgelements.Matrix:
        """Reconstructs the full transformation matrix used by SVGLoader."""
        cx, cy = self.width / 2, self.height / 2
        m = svgelements.Matrix()
        m.post_scale(self.state.zoom, self.state.zoom)
        m.post_rotate(math.radians(self.state.rotation), cx, cy)
        m.post_translate(self.state.x, self.state.y)
        return m

    def screen_to_world(self, sx: float, sy: float) -> Tuple[float, float]:
        """Converts screen coordinates to world (map) coordinates."""
        m = self._get_matrix()
        # Invert matrix to go Screen -> World
        im = ~m
        p = im.point_in_matrix_space((sx, sy))
        return p.x, p.y
