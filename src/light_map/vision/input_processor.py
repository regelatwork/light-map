from __future__ import annotations
import cv2
import numpy as np
import mediapipe as mp
from typing import List, Tuple, Any, TYPE_CHECKING

from light_map.core.scene import HandInput
from light_map.gestures import detect_gesture

if TYPE_CHECKING:
    from light_map.common_types import AppConfig


class InputProcessor:
    """Processes raw MediaPipe results into standardized HandInput objects."""

    def __init__(self, config: AppConfig):
        self.config = config

    def convert_mediapipe_to_inputs(
        self, results: Any, frame_shape: Tuple[int, int, int]
    ) -> List[HandInput]:
        """Converts raw MediaPipe results to a list of HandInput objects."""
        inputs = []
        if not results.multi_hand_landmarks or not results.multi_handedness:
            return inputs

        matrix = self.config.projector_matrix.astype(np.float32)

        for i, landmarks in enumerate(results.multi_hand_landmarks):
            handedness = results.multi_handedness[i]
            gesture = detect_gesture(
                landmarks.landmark, handedness.classification[0].label
            )

            tip = landmarks.landmark[mp.solutions.hands.HandLandmark.INDEX_FINGER_TIP]
            cam_point = np.array(
                [tip.x * frame_shape[1], tip.y * frame_shape[0]], dtype=np.float32
            ).reshape(1, 1, 2)

            if self.config.distortion_model:
                proj_point = self.config.distortion_model.apply_correction(cam_point)[
                    0
                ][0]
            else:
                proj_point = cv2.perspectiveTransform(cam_point, matrix)[0][0]

            inputs.append(
                HandInput(
                    gesture=gesture,
                    proj_pos=(int(proj_point[0]), int(proj_point[1])),
                    raw_landmarks=landmarks,
                )
            )
        return inputs
