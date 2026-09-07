"""
Calibration data models for dual-camera stereo vision.
"""

from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict, Field


class LensIntrinsics(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    matrix: np.ndarray = Field(..., description="3x3 Camera intrinsic matrix (K)")
    dist: np.ndarray = Field(..., description="Lens distortion coefficients")


class StereoExtrinsics(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    R: np.ndarray = Field(..., description="Rotation matrix R_stereo")
    t: np.ndarray = Field(..., description="Translation vector T_stereo")


class SensorROI(BaseModel):
    roi_left: tuple[int, int, int, int] = Field(..., description="[x, y, w, h] for left camera")
    roi_right: tuple[int, int, int, int] = Field(..., description="[x, y, w, h] for right camera")


class CalibrationResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    camera_left_intrinsics: LensIntrinsics
    camera_right_intrinsics: LensIntrinsics
    stereo_extrinsics: StereoExtrinsics
    projector_ppi: float
    roi_left: tuple[int, int, int, int]
    roi_right: tuple[int, int, int, int]
    table_homography: np.ndarray = Field(..., description="Homography matrix for tabletop Z=0")
    scale_factor: float = Field(..., description="Physical PPI scale factor")

    def __contains__(self, key: str) -> bool:
        if key in ("R", "t"):
            return hasattr(self.stereo_extrinsics, key)
        return hasattr(self, key)

    def __getitem__(self, key: str) -> Any:
        if key in ("R", "t"):
            return getattr(self.stereo_extrinsics, key)
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(key)
