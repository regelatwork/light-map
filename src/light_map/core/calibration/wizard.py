"""
Calibration wizard for unified stereo calibration and auto-discovery.
"""

import json
import logging

from light_map.core.calibration.models import CalibrationResult
from light_map.core.calibration.solver import SequentialSolver
from light_map.core.calibration.utils import get_marker_partition, resolve_lens_intrinsics
from light_map.core.config_store import ConfigStore


logger = logging.getLogger(__name__)


class CalibrationWizard:
    """
    Wizard to perform sequential stereo calibration and auto-discovery.
    """

    def __init__(self, tokens_json_path: str, calibration_data_dir: str = "calibration_data"):
        self.tokens_json_path = tokens_json_path
        self.calibration_data_dir = calibration_data_dir

        with open(tokens_json_path) as f:
            self.tokens_json = json.load(f)

        self.marker_partition = get_marker_partition()

    def _resolve_token_heights(self, token_ids: list[int]) -> dict[int, float]:
        """
        Resolves physical heights for a list of token IDs from tokens.json.
        """
        heights = {}
        for tid in token_ids:
            tid_str = str(tid)
            if tid_str not in self.tokens_json["aruco_defaults"]:
                continue

            config = self.tokens_json["aruco_defaults"][tid_str]
            h_mm = config.get("height_mm")

            if h_mm is not None:
                heights[tid] = float(h_mm)
            elif config.get("profile"):
                profile_name = config["profile"]
                profiles = self.tokens_json.get("token_profiles", {})
                if profile_name in profiles:
                    h_mm = profiles[profile_name].get("height_mm")
                    heights[tid] = float(h_mm) if h_mm is not None else 50.0
                else:
                    heights[tid] = 50.0
            else:
                heights[tid] = 50.0
        return {tid: h for tid, h in heights.items() if h > 0}

    def run_calibration(self, all_detections: list[dict]) -> CalibrationResult:
        """
        Executes the full calibration sequence.
        """
        # 1. Resolve Lens Intrinsics
        K_L, dist_L = resolve_lens_intrinsics("left")
        K_R, dist_R = resolve_lens_intrinsics("right")

        # 2. Initialize Solver
        solver = SequentialSolver(K_L, dist_L, K_R, dist_R)

        # 3. Group Detections
        projected_grid_detections = []
        ppi_ruler_detections = []
        token_detections = []

        for det in all_detections:
            if det.get("id") in self.marker_partition["projected_arena"]:
                projected_grid_detections.append(det)
            elif det.get("id") in self.marker_partition["ppi_ruler"]:
                ppi_ruler_detections.append(det)
            elif det.get("id") in self.marker_partition["user_tokens"]:
                token_detections.append(det)

        # 4. Resolve heights for tokens and then solve
        raw_token_ids = [d.get("id") for d in token_detections if d.get("id") is not None]
        heights = self._resolve_token_heights(raw_token_ids)

        valid_token_detections = []
        for d in token_detections:
            tid = d.get("id")
            if tid is not None and tid in heights and heights[tid] > 0:
                d["height_mm"] = heights[tid]
                valid_token_detections.append(d)

        result = solver.solve(
            projected_grid_detections,
            ppi_ruler_detections,
            valid_token_detections,
            self.tokens_json,
        )

        # 5. Save results
        self._save_calibration_result(result)

        return result

    def _save_calibration_result(self, result: CalibrationResult):
        """Saves the calibration result to stereo_calibration.json."""
        # Convert result to dict, handling numpy arrays
        data = {
            "camera_left_intrinsics": result.camera_left_intrinsics.model_dump(),
            "camera_right_intrinsics": result.camera_right_intrinsics.model_dump(),
            "stereo_extrinsics": {
                "R": result.stereo_extrinsics.R.tolist(),
                "t": result.stereo_extrinsics.t.tolist(),
            },
            "projector_ppi": result.projector_ppi,
            "roi_left": result.roi_left,
            "roi_right": result.roi_right,
            "table_homography": result.table_homography.tolist(),
            "scale_factor": result.scale_factor,
        }

        store = ConfigStore("stereo_calibration.json")
        store.save(data)
        logger.info("Calibration result saved to stereo_calibration.json")
