"""
Calibration data models for dual-camera stereo vision.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Any
import numpy as np

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
