"""
Module for the unified stereo calibration wizard.
"""

import numpy as np
import cv2
from pathlib import Path
from typing import List, Tuple, Dict
from .token_manager import TokenManager
from .intrinsics_loader import load_intrinsics
from .marker_detector import MarkerDetector
from .sequential_solver import SequentialSolver
from .roi_calculator import compute_roi_pass1, compute_roi_pass2

class StereoCalibrationWizard:
    def __init__(self, tokens_path: str, base_path: str, projector_matrix: np.ndarray = None, pattern_params: dict = None):
        self.token_manager = TokenManager(tokens_path)
        self.base_path = Path(base_path)
        self.marker_detector = MarkerDetector()
        self.projector_ppi = 0.0
        
        # Intrinsics
        self.k_left, self.dist_left = load_intrinsics("left", self.base_path)
        self.k_right, self.dist_right = load_intrinsics("right", self.base_path)
        
        # Solver
        self.solver = SequentialSolver(
            self.token_manager,
            self.projector_ppi,
            projector_matrix if projector_matrix is not None else np.eye(3),
            pattern_params if pattern_params is not None else {}
        )
        self.solver.k_left = self.k_left
        self.solver.dist_left = self.dist_left
        self.solver.k_right = self.k_right
        self.solver.dist_right = self.dist_right
        
    def run_calibration(self, left_image: np.ndarray, right_image: np.ndarray) -> Dict:
        h_l, w_l = left_image.shape[:2]
        h_r, w_r = right_image.shape[:2]

        # 1. Detect markers in both images
        left_markers = self.marker_detector.detect(left_image)
        right_markers = self.marker_detector.detect(right_image)

        # 2. Filter tokens.json for candidates (IDs 0-39)
        candidate_tokens = self.token_manager.get_candidate_tokens(range(40))
        token_heights = {t.id: t.height_mm for t in candidate_tokens}

        # 3. Phase 1: Table Scale & Z=0 Homography
        # Need to find markers 40, 41 (ruler) and 42-49 (grid)
        ruler_left = [m for m in left_markers if m[0] in [40, 41]]
        ruler_right = [m for m in right_markers if m[0] in [40, 41]]
        grid_left = [m for m in left_markers if m[0] in [42, 43, 44, 45, 46, 47, 48, 49]]
        grid_right = [m for m in right_markers if m[0] in [42, 43, 44, 45, 46, 47, 48, 49]]

        if len(ruler_left) < 2 or len(ruler_right) < 2:
            raise ValueError("Ruler markers not found in both images.")

        self.solver.solve_phase1_table_scale(ruler_left + grid_left, ruler_right + grid_right, ruler_distance_mm=100.0)

        # 4. Phase 2: Joint Non-Planar Stereo Extrinsics Solve
        # We need 12 points: 8 grid corners (42-49) + 4 tokens (0-3)
        l_corners_final = []
        r_corners_final = []

        # IDs in order
        target_ids = [42, 43, 44, 45, 46, 47, 48, 49, 0, 1, 2, 3]

        for tid in target_ids:
            l_m = next((m[1] for m in left_markers if m[0] == tid), None)
            r_m = next((m[1] for m in right_markers if m[0] == tid), None)

            if l_m is not None and r_m is not None:
                l_corners_final.append(l_m)
                r_corners_final.append(r_m)
            else:
                raise ValueError(f"Marker ID {tid} not found in one or both cameras.")

        self.solver.solve_phase2_stereo_extrinsics(
            l_corners_final, r_corners_final, token_heights
        )

        # 5. Phase 3: Auto-Discovery & Orientation Verification

        # 6. ROI Calculation
        roi_l, roi_r = compute_roi_pass2(
            (h_l, w_l),
            self.solver.camera_left_extrinsics, self.solver.camera_left_t,
            self.solver.camera_right_extrinsics, self.solver.camera_right_t, 200.0,
            corners_3d=self.solver.grid_corners_3d,
            k_left=self.k_left,
            k_right=self.k_right
        )

        left_id, right_id = self.solver.solve_phase3_auto_discovery()

        # If tx < 0, the camera that produced right_image is the left camera.
        # So roi_r is the left ROI, and roi_l is the right ROI.
        if self.solver.t_stereo[0] < 0:
            roi_l, roi_r = roi_r, roi_l

        return {
            "roi_left": roi_l,
            "roi_right": roi_r,
            "r_stereo": self.solver.r_stereo,
            "t_stereo": self.solver.t_stereo,
            "left_id": left_id,
            "right_id": right_id
        }

