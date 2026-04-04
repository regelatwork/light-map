from typing import List, Tuple, Set, TYPE_CHECKING
import numpy as np
import cv2
from .common_types import Layer, ImagePatch, LayerMode
from .display_utils import draw_text_with_background

if TYPE_CHECKING:
    from .core.world_state import WorldState

# --- Calibration Pattern Colors (BGRA) ---
CALIB_BG_COLOR = (255, 255, 255, 255)
CALIB_BORDER_COLOR = (0, 0, 0, 255)
CALIB_TABLE_MARKER_COLOR = (0, 0, 0, 255)
CALIB_BOX_MARKER_COLOR = (0, 0, 0, 255)
CALIB_BOX_OUTLINE_COLOR = (60, 60, 60, 255)


class Projector3DPatternLayer(Layer):
    """
    Renders the static calibration pattern (ArUco markers and box outline).
    Only re-renders when the target box moves to a new position.
    """

    def __init__(
        self,
        state: "WorldState",
        width: int,
        height: int,
        box_markers: List[Tuple[int, np.ndarray]] = None,
        table_markers: List[Tuple[int, np.ndarray]] = None,
        box_outline: np.ndarray = None,
    ):
        # is_static=True means it uses the versioning system to cache its output
        super().__init__(state=state, is_static=True, layer_mode=LayerMode.BLOCKING)
        self.width = width
        self.height = height
        self.box_markers = box_markers or []
        self.table_markers = table_markers or []
        self.box_outline = box_outline
        self._aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)

    def get_current_version(self) -> int:
        return self.state.calibration_version if self.state else 0

    def _generate_patches(self, current_time: float) -> List[ImagePatch]:
        if self.width <= 0 or self.height <= 0:
            return []

        # Create full white background (BGRA) for better projector-camera visibility
        img = np.full((self.height, self.width, 4), CALIB_BG_COLOR, dtype=np.uint8)
        img[:, :, 3] = CALIB_BG_COLOR[3]

        # Draw a dark border (BGRA)
        cv2.rectangle(
            img, (5, 5), (self.width - 6, self.height - 6), CALIB_BORDER_COLOR, 10
        )

        # Draw Table Markers (Reference) - Dark Green (BGRA)
        for aruco_id, corners in self.table_markers:
            self._draw_marker(img, aruco_id, corners, CALIB_TABLE_MARKER_COLOR)

        # Draw Box Markers (Target) - Dark Blue (BGRA)
        for aruco_id, corners in self.box_markers:
            self._draw_marker(img, aruco_id, corners, CALIB_BOX_MARKER_COLOR)

        # Draw Box Outline if provided - Dark Gray
        if self.box_outline is not None:
            cv2.polylines(
                img,
                [self.box_outline.astype(np.int32)],
                True,
                CALIB_BOX_OUTLINE_COLOR,
                2,
            )

        return [ImagePatch(0, 0, self.width, self.height, img)]

    def _draw_marker(self, img, aruco_id, corners, color):
        marker_size = int(np.linalg.norm(corners[0] - corners[1]))
        if marker_size < 10:
            return

        # Generate the marker bits
        marker_img = cv2.aruco.generateImageMarker(
            self._aruco_dict, aruco_id, marker_size
        )
        marker_bgr = cv2.cvtColor(marker_img, cv2.COLOR_GRAY2BGR)

        # Create a thicker white border/background for contrast
        # Increased padding from 4 to 12 to give a larger quiet zone for detection
        padding = 12
        padded_marker = np.full(
            (marker_size + padding, marker_size + padding, 3), 255, dtype=np.uint8
        )
        padded_marker[
            padding // 2 : padding // 2 + marker_size,
            padding // 2 : padding // 2 + marker_size,
        ] = marker_bgr

        # Warp marker to the designated corners
        src_pts = np.array(
            [
                [0, 0],
                [marker_size + padding, 0],
                [marker_size + padding, marker_size + padding],
                [0, marker_size + padding],
            ],
            dtype=np.float32,
        )
        # Add slight padding to the target corners to match the border
        M = cv2.getPerspectiveTransform(src_pts, corners.astype(np.float32))

        # We warp onto a temporary layer then composite
        temp = cv2.warpPerspective(padded_marker, M, (self.width, self.height))

        # Composite: use a mask of where the marker is warped to ensure all pixels (including black) are copied
        mask_src = np.full(
            (marker_size + padding, marker_size + padding), 255, dtype=np.uint8
        )
        mask_warped = cv2.warpPerspective(mask_src, M, (self.width, self.height))
        mask = mask_warped > 0

        img[mask, :3] = temp[mask]

        # Draw ID for debugging/info - Move below the marker
        # corners are [TL, TR, BR, BL]
        bl = corners[3]
        br = corners[2]
        bottom_center = ((bl + br) / 2).astype(int)

        cv2.putText(
            img,
            str(aruco_id),
            (bottom_center[0] - 10, bottom_center[1] + 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color[:3],
            2,
        )


class Projector3DFeedbackLayer(Layer):
    """
    Renders dynamic feedback (detection indicators and instructions).
    Re-renders every frame to show real-time detection status.
    """

    def __init__(
        self,
        state: "WorldState",
        width: int,
        height: int,
        box_markers: List[Tuple[int, np.ndarray]] = None,
        table_markers: List[Tuple[int, np.ndarray]] = None,
        instructions: str = "",
        instruction_pos: Tuple[int, int] = (100, 100),
    ):
        super().__init__(state=state, is_static=False, layer_mode=LayerMode.NORMAL)
        self.width = width
        self.height = height
        self.box_markers = box_markers or []
        self.table_markers = table_markers or []
        self.instructions = instructions
        self.instruction_pos = instruction_pos
        self.detected_ids: Set[int] = set()

    def get_current_version(self) -> int:
        if self.state is None:
            return 0
        return max(self.state.scene_version, self.state.system_time_version)

    def _generate_patches(self, current_time: float) -> List[ImagePatch]:
        if self.width <= 0 or self.height <= 0:
            return []

        # Use a transparent background for NORMAL blending
        img = np.zeros((self.height, self.width, 4), dtype=np.uint8)

        # Draw Detection Indicators for both sets of markers
        all_markers = self.table_markers + self.box_markers
        for aruco_id, corners in all_markers:
            if aruco_id in self.detected_ids:
                self._draw_detection_indicator(img, corners)

        # Draw Instructions
        if self.instructions:
            draw_text_with_background(
                img,
                self.instructions,
                self.instruction_pos,
                scale=1.0,
                thickness=2,
                color=(255, 255, 255, 255),
                bg_color=(0, 0, 128),
                alpha=0.9,
            )

        return [ImagePatch(0, 0, self.width, self.height, img)]

    def _draw_detection_indicator(self, img, corners):
        tl = corners[0]
        center = np.mean(corners, axis=0)
        vec = tl - center
        pos = (tl + vec * 0.2).astype(int)

        cv2.circle(img, (pos[0], pos[1]), 8, (0, 255, 0, 255), -1)
        cv2.circle(img, (pos[0], pos[1]), 10, (255, 255, 255, 255), 2)
