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
        thickness_multiplier: float = 3.0,
    ):
        super().__init__(state=state, is_static=True, layer_mode=LayerMode.NORMAL)
        self.visibility_engine = visibility_engine
        self.width = width
        self.height = height
        self.thickness_multiplier = thickness_multiplier
        self._last_geometry_version = -1

    def get_current_version(self) -> int:
        if self.state is None:
            return 0
        return max(self.state.visibility_timestamp, self.state.viewport_timestamp)

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
        # Walls in visibility mask are 2px thick in mask space.
        # Mask space is 16px per grid unit. SVG space is 'spacing' px per grid unit.
        # So 1 mask pixel = (spacing / 16.0) SVG pixels.
        # In screen space, that is (spacing / 16.0) * vp.zoom pixels.
        spacing = self.visibility_engine.grid_spacing_svg
        base_wall_thickness = (spacing / 16.0) * vp.zoom

        # Yellow line: Base thickness * multiplier, min 2px
        yellow_thickness = max(2, int(base_wall_thickness * self.thickness_multiplier))
        # Black outline: Yellow + padding, min 4px
        # We add 2px in mask-space equivalent: 2.0 * (spacing / 16.0) * vp.zoom
        padding = max(2, int(2.0 * (spacing / 16.0) * vp.zoom))
        black_thickness = yellow_thickness + padding

        # Circle radius: Roughly 0.8x the yellow line thickness, min 3px
        circle_radius = max(3, int(yellow_thickness * 0.8))
        circle_outline = circle_radius + max(2, int(padding / 2))

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
                    cv2.circle(
                        image, pt, circle_outline, BLACK, -1, lineType=cv2.LINE_AA
                    )
                    # Yellow center
                    cv2.circle(
                        image, pt, circle_radius, YELLOW, -1, lineType=cv2.LINE_AA
                    )
            else:
                # Render as thick yellow line with black outline
                pts_array = np.array(points, dtype=np.int32).reshape((-1, 1, 2))

                # Black outline
                cv2.polylines(
                    image,
                    [pts_array],
                    False,
                    BLACK,
                    thickness=black_thickness,
                    lineType=cv2.LINE_AA,
                )
                # Yellow line
                cv2.polylines(
                    image,
                    [pts_array],
                    False,
                    YELLOW,
                    thickness=yellow_thickness,
                    lineType=cv2.LINE_AA,
                )

        return [
            ImagePatch(
                x=0,
                y=0,
                width=self.width,
                height=self.height,
                data=image,
            )
        ]
