from typing import TYPE_CHECKING, Optional

import numpy as np

from light_map.core.common_types import Token, TokenDetectionAlgorithm
from light_map.map.map_system import MapSystem
from light_map.vision.detectors.aruco_detector import ArucoTokenDetector
from light_map.vision.detectors.flash_detector import FlashTokenDetector
from light_map.vision.detectors.structured_light_detector import (
    StructuredLightTokenDetector,
)


if TYPE_CHECKING:
    from light_map.rendering.projection import ProjectionService, Projector3DModel
    from light_map.rendering.projector import ProjectorDistortionModel


class TokenTracker:
    # Expose constants for backward compatibility if needed,
    # though ideally consumers should not rely on them.
    # We can alias them from the new modules if strictly necessary,
    # but for now let's assume external code doesn't access them directly
    # or we will fix it if tests fail.

    def __init__(self):
        self._debug_mode = False
        self._flash_detector = FlashTokenDetector(debug_mode=self._debug_mode)
        self._sl_detector = StructuredLightTokenDetector(debug_mode=self._debug_mode)
        self._aruco_detector = ArucoTokenDetector(debug_mode=self._debug_mode)

    @property
    def debug_mode(self):
        return self._debug_mode

    @debug_mode.setter
    def debug_mode(self, value: bool):
        self._debug_mode = value
        if hasattr(self, "_flash_detector"):
            self._flash_detector.debug_mode = value
        if hasattr(self, "_sl_detector"):
            self._sl_detector.debug_mode = value
        if hasattr(self, "_aruco_detector"):
            self._aruco_detector.debug_mode = value

    def get_scan_pattern(
        self, width: int, height: int, ppi: float
    ) -> tuple[np.ndarray, list[tuple[int, int]]]:
        """
        Generates a jittered staggered (hexagonal) dot grid pattern for optimal coverage.
        Delegates to StructuredLightDetector.
        """
        return self._sl_detector.get_scan_pattern(width, height, ppi)

    def set_aruco_calibration(
        self,
        camera_matrix: np.ndarray | None = None,
        distortion_coefficients: np.ndarray | None = None,
        rotation_vector: np.ndarray | None = None,
        translation_vector: np.ndarray | None = None,
    ):
        if camera_matrix is not None and distortion_coefficients is not None:
            self._aruco_detector.set_calibration(camera_matrix, distortion_coefficients)
            self._flash_detector.set_calibration(camera_matrix, distortion_coefficients)
            self._sl_detector.set_calibration(camera_matrix, distortion_coefficients)
        if rotation_vector is not None and translation_vector is not None:
            self._aruco_detector.set_extrinsics(rotation_vector, translation_vector)
            self._flash_detector.set_extrinsics(rotation_vector, translation_vector)
            self._sl_detector.set_extrinsics(rotation_vector, translation_vector)

    def detect_tokens(
        self,
        frame_white: np.ndarray | None = None,
        frame_pattern: np.ndarray | None = None,
        frame_dark: np.ndarray | None = None,
        projector_matrix: np.ndarray | None = None,
        map_system: MapSystem | None = None,
        grid_spacing_svg: float = 0.0,
        grid_origin_x: float = 0.0,
        grid_origin_y: float = 0.0,
        mask_rois: list[tuple[int, int, int, int]] | None = None,
        ppi: float = 96.0,
        algorithm: TokenDetectionAlgorithm = TokenDetectionAlgorithm.FLASH,
        token_configs: dict[int, dict] | None = None,
        default_height_mm: float = 0.0,
        distortion_model: Optional["ProjectorDistortionModel"] = None,
        projector_3d_model: Optional["Projector3DModel"] = None,
        projection_service: Optional["ProjectionService"] = None,
    ) -> list[Token]:
        # Handle case where only one frame is passed (default to frame_pattern for SL or frame_white for Flash)
        if frame_pattern is None and frame_white is not None:
            frame_pattern = frame_white
        if frame_white is None and frame_pattern is not None:
            frame_white = frame_pattern

        if frame_white is None:
            return []

        if algorithm == TokenDetectionAlgorithm.ARUCO:
            return self._aruco_detector.detect(
                frame_white,
                map_system,
                token_configs=token_configs,
                ppi=ppi,
                default_height_mm=default_height_mm,
                projector_matrix=projector_matrix,
                projection_service=projection_service,
            )

        if (
            algorithm == TokenDetectionAlgorithm.STRUCTURED_LIGHT
            and frame_dark is not None
        ):
            w_proj = map_system.width
            h_proj = map_system.height
            _, expected_points = self.get_scan_pattern(w_proj, h_proj, ppi)

            return self._sl_detector.detect(
                frame_pattern,
                frame_dark,
                expected_points,
                projector_matrix,
                map_system,
                grid_spacing_svg,
                grid_origin_x,
                grid_origin_y,
                mask_rois,
                ppi=ppi,
                default_height_mm=default_height_mm,
                distortion_model=distortion_model,
                projector_3d_model=projector_3d_model,
            )
        else:
            return self._flash_detector.detect(
                frame_white,
                projector_matrix,
                map_system,
                grid_spacing_svg,
                grid_origin_x,
                grid_origin_y,
                mask_rois,
                ppi=ppi,
                default_height_mm=default_height_mm,
                distortion_model=distortion_model,
                projector_3d_model=projector_3d_model,
            )
