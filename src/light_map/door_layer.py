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
                # Render endpoints as 3px yellow circles with black outlines
                for pt in points:
                    # Black outline (4px)
                    cv2.circle(image, pt, 4, BLACK, -1, lineType=cv2.LINE_AA)
                    # Yellow center (3px)
                    cv2.circle(image, pt, 3, YELLOW, -1, lineType=cv2.LINE_AA)
            else:
                # Render as yellow line with black outline
                pts_array = np.array(points, dtype=np.int32).reshape((-1, 1, 2))

                # Black outline (3px)
                cv2.polylines(
                    image, [pts_array], False, BLACK, thickness=3, lineType=cv2.LINE_AA
                )
                # Yellow line (1px)
                cv2.polylines(
                    image, [pts_array], False, YELLOW, thickness=1, lineType=cv2.LINE_AA
                )

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
