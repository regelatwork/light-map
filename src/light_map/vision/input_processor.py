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

    def _project_to_projector(self, cam_pts: np.ndarray, frame_shape: Tuple[int, int, int]) -> np.ndarray:
        """Helper to project camera pixels to projector space."""
        # 1. 3D Model Projection
        if (
            self.config.projector_3d_model
            and self.config.projector_3d_model.use_3d
        ):
            # Reconstruct world points at Z=0
            if (
                self.config.camera_matrix is not None
                and self.config.rvec is not None
                and self.config.tvec is not None
            ):
                try:
                    mtx_inv = np.linalg.inv(self.config.camera_matrix)
                    rvec = np.array(self.config.rvec).reshape(3, 1)
                    tvec = np.array(self.config.tvec).reshape(3, 1)
                    R, _ = cv2.Rodrigues(rvec)
                    RT = R.T
                    camera_center = -(RT @ tvec).flatten()
                    
                    pts_homog = np.hstack([cam_pts, np.ones((cam_pts.shape[0], 1))])
                    rays_cam = mtx_inv @ pts_homog.T
                    rays_world = RT @ rays_cam
                    
                    cz = camera_center[2]
                    vz = rays_world[2, :]
                    s = (0.0 - cz) / (vz + 1e-9)
                    p_world = camera_center.reshape(3, 1) + s * rays_world
                    return self.config.projector_3d_model.project_world_to_projector(p_world.T)
                except Exception:
                    pass

        # 2. Fallback to Homography
        cam_pts_reshaped = cam_pts.reshape(-1, 1, 2).astype(np.float32)
        if self.config.distortion_model:
            proj_pts = self.config.distortion_model.apply_correction(cam_pts_reshaped)
        else:
            proj_pts = cv2.perspectiveTransform(cam_pts_reshaped, self.config.projector_matrix)
        return proj_pts.reshape(-1, 2)

    def convert_mediapipe_to_inputs(
        self, results: Any, frame_shape: Tuple[int, int, int]
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

            tip_lm = landmarks.landmark[mp.solutions.hands.HandLandmark.INDEX_FINGER_TIP]
            cam_point = np.array(
                [[tip_lm.x * frame_shape[1], tip_lm.y * frame_shape[0]]], dtype=np.float32
            )

            proj_point = self._project_to_projector(cam_point, frame_shape)[0]
            px, py = int(proj_point[0]), int(proj_point[1])

            # Virtual Pointer Direction Calculation (POINTING)
            from light_map.common_types import GestureType

            ux, uy = 0.0, 0.0
            if gesture == GestureType.POINTING:
                # Calculate direction from PIP to TIP
                pip_lm = landmarks.landmark[
                    mp.solutions.hands.HandLandmark.INDEX_FINGER_PIP
                ]

                # Direction in camera coordinates (normalized)
                dx_cam = tip_lm.x - pip_lm.x
                dy_cam = tip_lm.y - pip_lm.y
                mag = np.sqrt(dx_cam**2 + dy_cam**2)

                if mag > 0.0001:
                    # Approximate transformation of the direction vector to projector space
                    # Let's project another point 10% further along the finger ray
                    tip_ext_cam = np.array(
                        [
                            [(tip_lm.x + (dx_cam / mag) * 0.1) * frame_shape[1],
                             (tip_lm.y + (dy_cam / mag) * 0.1) * frame_shape[0]]
                        ],
                        dtype=np.float32,
                    )

                    proj_ext = self._project_to_projector(tip_ext_cam, frame_shape)[0]

                    # Direction in projector space
                    pdx = proj_ext[0] - proj_point[0]
                    pdy = proj_ext[1] - proj_point[1]
                    pmag = np.sqrt(pdx**2 + pdy**2)

                    if pmag > 0.0001:
                        ux = pdx / pmag
                        uy = pdy / pmag

            # --- VIRTUAL CURSOR POSITION ---
            cursor_pos = None
            if gesture == GestureType.POINTING:
                ppi = getattr(self.config, "projector_ppi", 96.0)
                ext = getattr(self.config, "pointer_extension_inches", 2.0)
                cx = int(px + ux * ppi * ext)
                cy = int(py + uy * ppi * ext)
                cursor_pos = (cx, cy)

            # Input Masking (Filter by GM Position)
            if self.hand_masker.is_point_masked(px, py, self.config.gm_position, res):
                continue

            hi = HandInput(
                gesture=gesture,
                proj_pos=(px, py),
                unit_direction=(ux, uy),
                raw_landmarks=landmarks,
            )
            hi.cursor_pos = cursor_pos
            inputs.append(hi)
        return inputs
