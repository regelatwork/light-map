from __future__ import annotations
import cv2
import numpy as np
import mediapipe as mp
from typing import List, Tuple, Any, Dict, TYPE_CHECKING

from light_map.core.scene import HandInput
from light_map.gestures import detect_gesture
from light_map.vision.hand_masker import HandMasker

if TYPE_CHECKING:
    from light_map.common_types import AppConfig


class DummyResults:
    """Wraps raw landmark and handedness dictionaries to mimic MediaPipe results."""

    def __init__(
        self,
        hands_list: List[List[Dict[str, float]]],
        handedness_list: List[Dict[str, Any]],
    ):
        self.multi_hand_landmarks = []
        self.multi_handedness = []

        for hl in hands_list:

            class DummyHandLandmarks:
                def __init__(self, lm_dicts):
                    class DummyLandmark:
                        def __init__(self, d):
                            self.x = d.get("x", 0)
                            self.y = d.get("y", 0)
                            self.z = d.get("z", 0)

                    self.landmark = [DummyLandmark(d) for d in lm_dicts]

            self.multi_hand_landmarks.append(DummyHandLandmarks(hl))

        for h in handedness_list:

            class DummyHandedness:
                def __init__(self, h_dict):
                    class DummyClassification:
                        def __init__(self, d):
                            self.label = d.get("label", "Left")
                            self.score = d.get("score", 1.0)

                    self.classification = [DummyClassification(h_dict)]

            self.multi_handedness.append(DummyHandedness(h))


class InputProcessor:
    """Processes raw MediaPipe results into standardized HandInput objects."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.hand_masker = HandMasker()

    def convert_mediapipe_to_inputs(
        self, results: Any, frame_shape: Tuple[int, int, int]
    ) -> List[HandInput]:
        """Converts raw MediaPipe results to a list of HandInput objects."""
        inputs = []
        if not results.multi_hand_landmarks or not results.multi_handedness:
            return inputs

        matrix = self.config.projector_matrix.astype(np.float32)
        res = (self.config.width, self.config.height)

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

            px, py = int(proj_point[0]), int(proj_point[1])

            # Input Masking (Filter by GM Position)
            if self.hand_masker.is_point_masked(px, py, self.config.gm_position, res):
                continue

            inputs.append(
                HandInput(
                    gesture=gesture,
                    proj_pos=(px, py),
                    raw_landmarks=landmarks,
                )
            )
        return inputs
