from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple


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
        Adjust zoom level.
        If center_x/y are provided, adjusts x/y to zoom into that point.
        """
        if center_x is None:
            center_x = self.width / 2
        if center_y is None:
            center_y = self.height / 2

        old_zoom = self.state.zoom
        self.state.zoom *= factor

        # Adjust pan to keep center_x/y pinned
        # New_X = (Old_X - center) * (new_zoom/old_zoom) + center?
        # Actually, simpler:
        # The point under the cursor (center_x, center_y) should remain at the same SVG coordinate.
        # SVG_X = (Screen_X - Pan_X) / Zoom

        # (center_x - new_pan_x) / new_zoom = (center_x - old_pan_x) / old_zoom
        # new_pan_x = center_x - (center_x - old_pan_x) * (new_zoom / old_zoom)

        ratio = self.state.zoom / old_zoom
        self.state.x = center_x - (center_x - self.state.x) * ratio
        self.state.y = center_y - (center_y - self.state.y) * ratio

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

    def screen_to_world(self, sx: float, sy: float) -> Tuple[float, float]:
        """Converts screen coordinates to world (map) coordinates."""
        # Screen = World * Zoom + Pan
        # World = (Screen - Pan) / Zoom
        wx = (sx - self.state.x) / self.state.zoom
        wy = (sy - self.state.y) / self.state.zoom
        return wx, wy
