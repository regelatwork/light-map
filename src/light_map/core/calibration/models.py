"""
Calibration data models for dual-camera stereo vision.
Backward-compatible re-exports from canonical light_map.calibration.models.
"""

from light_map.calibration.models import (
    CalibrationResult,
    LensIntrinsics,
    SensorROI,
    StereoExtrinsics,
)


__all__ = [
    "CalibrationResult",
    "LensIntrinsics",
    "SensorROI",
    "StereoExtrinsics",
]
