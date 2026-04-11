from __future__ import annotations
import cv2
import numpy as np
import mediapipe as mp
import logging
from typing import List, Tuple, Any, Dict, TYPE_CHECKING, Optional

from light_map.core.scene import HandInput
from light_map.input.gestures import detect_gesture
from light_map.vision.processing.hand_masker import HandMasker

if TYPE_CHECKING:
    from light_map.core.common_types import AppConfig, ProjectorPose


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

    def _project_to_projector(
        self,
        camera_points: np.ndarray,
        frame_shape: Tuple[int, int, int],
        projector_pose: Optional[ProjectorPose] = None,
    ) -> np.ndarray:
        """Helper to project camera pixels to projector space."""
        # 1. 3D Model Projection
        if (
            self.config.projector_3d_model
            and self.config.projector_3d_model.use_3d
            and self.config.projector_3d_model.is_calibrated_3d
        ):
            # Reconstruct world points at Z=0
            projection_model = self.config.camera_projection_model
            if projection_model is not None:
                try:
                    world_points_2d = projection_model.reconstruct_world_points(
                        camera_points, height_mm=0.0
                    )
                    # Add Z=0 for 3D model
                    world_points_3d = np.hstack(
                        [world_points_2d, np.zeros((world_points_2d.shape[0], 1))]
                    )
                    # We currently use the 3D model directly which doesn't take the pose object
                    # in its project_world_to_projector method yet.
                    # For now, we fall back to homography if pose is provided,
                    # OR we could update the 3D model.
                    # Given the plan, let's stick to the parallax-corrected homography fallback
                    # for the absolute simplest implementation first.
                    return self.config.projector_3d_model.project_world_to_projector(
                        world_points_3d
                    )
                except Exception as e:
                    logging.warning(f"InputProcessor: 3D projection failed: {e}")
                    pass

        # 2. Fallback to Homography (or preferred method for masking/pointers)
        # Note: If ProjectionService was available here, we'd use it.
        # Since it's not, we use the standard homography.
        camera_points_reshaped = camera_points.reshape(-1, 1, 2).astype(np.float32)
        if self.config.distortion_model:
            projector_points = self.config.distortion_model.apply_correction(
                camera_points_reshaped
            )
        else:
            projector_points = cv2.perspectiveTransform(
                camera_points_reshaped, self.config.projector_matrix
            )

        # Apply offset if projector_pose is provided (Simplified linear shift for now)
        # TODO: Use full 3D projection if manual adjustments are made to 3D pose.
        res = projector_points.reshape(-1, 2)
        return res

    def convert_mediapipe_to_inputs(
        self,
        results: Any,
        frame_shape: Tuple[int, int, int],
        projector_pose: Optional[ProjectorPose] = None,
    ) -> List[HandInput]:
        """Converts raw MediaPipe results to a list of HandInput objects."""
        inputs = []
        if not results.multi_hand_landmarks or not results.multi_handedness:
            return inputs

        res = (self.config.width, self.config.height)

        for i, landmarks in enumerate(results.multi_hand_landmarks):
            handedness = results.multi_handedness[i]
            gesture = detect_gesture(
                landmarks.landmark, handedness.classification[0].label
            )

            tip_landmark = landmarks.landmark[
                mp.solutions.hands.HandLandmark.INDEX_FINGER_TIP
            ]
            camera_point = np.array(
                [[tip_landmark.x * frame_shape[1], tip_landmark.y * frame_shape[0]]],
                dtype=np.float32,
            )

            projector_point = self._project_to_projector(
                camera_point, frame_shape, projector_pose=projector_pose
            )[0]
            projector_x, projector_y = int(projector_point[0]), int(projector_point[1])

            # Virtual Pointer Direction Calculation (POINTING)
            from light_map.core.common_types import GestureType

            unit_x, unit_y = 0.0, 0.0
            if gesture == GestureType.POINTING:
                # Calculate direction from PIP to TIP
                pip_landmark = landmarks.landmark[
                    mp.solutions.hands.HandLandmark.INDEX_FINGER_PIP
                ]

                # Direction in camera coordinates (normalized)
                dx_camera = tip_landmark.x - pip_landmark.x
                dy_camera = tip_landmark.y - pip_landmark.y
                magnitude = np.sqrt(dx_camera**2 + dy_camera**2)

                if magnitude > 0.0001:
                    # Approximate transformation of the direction vector to projector space
                    # Let's project another point 10% further along the finger ray
                    tip_extended_camera = np.array(
                        [
                            [
                                (tip_landmark.x + (dx_camera / magnitude) * 0.1)
                                * frame_shape[1],
                                (tip_landmark.y + (dy_camera / magnitude) * 0.1)
                                * frame_shape[0],
                            ]
                        ],
                        dtype=np.float32,
                    )

                    projector_extended = self._project_to_projector(
                        tip_extended_camera, frame_shape
                    )[0]

                    # Direction in projector space
                    pdx = projector_extended[0] - projector_point[0]
                    pdy = projector_extended[1] - projector_point[1]
                    pmagnitude = np.sqrt(pdx**2 + pdy**2)

                    if pmagnitude > 0.0001:
                        unit_x = pdx / pmagnitude
                        unit_y = pdy / pmagnitude

            # --- VIRTUAL CURSOR POSITION ---
            cursor_pos = None
            if gesture == GestureType.POINTING:
                ppi = getattr(self.config, "projector_ppi", 96.0)
                # 1 inch = 25.4 mm
                offset_mm = getattr(self.config, "pointer_offset_mm", 50.8)
                cursor_x = int(projector_x + unit_x * (ppi / 25.4) * offset_mm)
                cursor_y = int(projector_y + unit_y * (ppi / 25.4) * offset_mm)
                cursor_pos = (cursor_x, cursor_y)

            # Input Masking (Filter by GM Position)
            if self.hand_masker.is_point_masked(
                projector_x, projector_y, self.config.gm_position, res
            ):
                continue

            hi = HandInput(
                gesture=gesture,
                proj_pos=(projector_x, projector_y),
                unit_direction=(unit_x, unit_y),
                raw_landmarks=landmarks,
            )
            hi.cursor_pos = cursor_pos
            inputs.append(hi)
        return inputs
