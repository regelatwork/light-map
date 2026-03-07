import cv2
import numpy as np
import math
import svgelements
from typing import List
from .common_types import Layer, ImagePatch, LayerMode
from .core.world_state import WorldState
from .visibility_engine import VisibilityEngine
from .visibility_types import VisibilityType


class DoorLayer(Layer):
    """
    Renders door highlights on the map.
    Closed doors: Yellow line with black outline.
    Open doors: Yellow circles at endpoints with black outlines.
    """

    def __init__(
        self,
        state: WorldState,
        visibility_engine: VisibilityEngine,
        width: int,
        height: int,
    ):
        super().__init__(state=state, layer_mode=LayerMode.NORMAL)
        self.visibility_engine = visibility_engine
        self.width = width
        self.height = height
        self._last_geometry_version = -1

    @property
    def is_dirty(self) -> bool:
        if self.state is None:
            return True
        return (
            self.visibility_engine.geometry_version > self._last_geometry_version
            or self.state.viewport_timestamp > self._last_state_timestamp
        )

    def _generate_patches(self, current_time: float) -> List[ImagePatch]:
        # Create transparent base
        image = np.zeros((self.height, self.width, 4), dtype=np.uint8)

        if not self.state.viewport:
            return []

        vp = self.state.viewport
        cx, cy = self.width / 2, self.height / 2

        # Transformation Matrix: SVG -> Screen
        m_svg_to_screen = svgelements.Matrix()
        m_svg_to_screen.post_scale(vp.zoom, vp.zoom)
        m_svg_to_screen.post_rotate(math.radians(vp.rotation), cx, cy)
        m_svg_to_screen.post_translate(vp.x, vp.y)

        # Dynamic Thickness Calculation
        # Walls in visibility mask are 2px thick in mask space (16px = 1 grid unit).
        # In screen space, that translates roughly to 2.0 * vp.zoom pixels.
        # We want doors to be thicker to avoid light leaks and ensure they are seen.
        base_wall_thickness = 2.0 * vp.zoom

        # Yellow line: 1.5x thicker than wall, min 2px
        yellow_thickness = max(2, int(base_wall_thickness * 1.5))
        # Black outline: Yellow + 4px extra, min 4px
        black_thickness = yellow_thickness + max(2, int(2 * vp.zoom))

        # Circle radius: Roughly 0.75x the yellow line thickness, min 3px
        circle_radius = max(3, int(yellow_thickness * 0.8))
        circle_outline = circle_radius + max(2, int(1 * vp.zoom))

        # Colors (BGRA)
        YELLOW = (0, 255, 255, 255)
        BLACK = (0, 0, 0, 255)

        for blocker in self.visibility_engine.blockers:
            if blocker.type != VisibilityType.DOOR:
                continue

            # Transform segments
            points = []
            for sx, sy in blocker.segments:
                p = m_svg_to_screen.point_in_matrix_space((sx, sy))
                points.append((int(p.x), int(p.y)))

            if len(points) < 2:
                continue

            if blocker.is_open:
                # Render endpoints as circles
                for pt in points:
                    # Black outline
                    cv2.circle(image, pt, circle_outline, BLACK, -1, lineType=cv2.LINE_AA)
                    # Yellow center
                    cv2.circle(image, pt, circle_radius, YELLOW, -1, lineType=cv2.LINE_AA)
            else:
                # Render as thick yellow line with black outline
                pts_array = np.array(points, dtype=np.int32).reshape((-1, 1, 2))

                # Black outline
                cv2.polylines(image, [pts_array], False, BLACK, thickness=black_thickness, lineType=cv2.LINE_AA)
                # Yellow line
                cv2.polylines(image, [pts_array], False, YELLOW, thickness=yellow_thickness, lineType=cv2.LINE_AA)
        self._last_geometry_version = self.visibility_engine.geometry_version
        self._update_timestamp()

        return [
            ImagePatch(
                x=0,
                y=0,
                width=self.width,
                height=self.height,
                data=image,
            )
        ]

    def _update_timestamp(self):
        if self.state:
            self._last_state_timestamp = self.state.viewport_timestamp
