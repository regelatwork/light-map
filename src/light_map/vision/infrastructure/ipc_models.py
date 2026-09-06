import struct
import numpy as np
from dataclasses import dataclass
from typing import Any, Optional

# Shared Memory Slot Binary Header (Struct Format: '<qqiiiii')
# Fields:
# 1. frame_index   (int64_t): Monotonic frame sequence counter
# 2. timestamp_ns  (int64_t): Hardware capture timestamp (time.monotonic_ns())
# 3. width         (int32_t): Active frame width in pixels (e.g. 1920 or 4608)
# 4. height        (int32_t): Active frame height in pixels (e.g. 1080 or 2592)
# 5. roi_offset_x  (int32_t): Sensor crop horizontal offset in original sensor pixels
# 6. roi_offset_y  (int32_t): Sensor crop vertical offset in original sensor pixels
# 7. status        (int32_t): Stream status (0: normal, 1: transitioning)
FrameHeader = struct.Struct("<qqiiiii" + "x" * 28)

def unpack_frame_header(buffer: bytes, offset: int = 0) -> tuple:
    return struct.unpack_from(FrameHeader.format, buffer, offset)

def pack_frame_header(header: tuple, buffer: bytes, offset: int):
    FrameHeader.pack_into(buffer, offset, *header)

@dataclass
class SetRoiCommand:
    crop_x: int
    crop_y: int
    crop_w: int
    crop_h: int

@dataclass
class SetFullFrameCommand:
    pass

@dataclass
class ShutdownCommand:
    pass

@dataclass
class Token3DState:
    id: str
    name: str
    type: str  # "PC" or "NPC"
    world_x: float  # Tabletop X in mm
    world_y: float  # Tabletop Y in mm
    world_z: float  # Elevation height in mm
    is_stereo_triangulated: bool
    last_seen_ns: int

@dataclass
class StereoDiagnostics:
    left_camera_fps: float
    right_camera_fps: float
    stereo_match_ratio: float  # Percentage of matched stereo pairs vs single-cam fallbacks
    active_mode: str  # "FULL_FRAME" vs "HIGH_SPEED_ROI"

@dataclass
class ArUcoMarker2D:
    marker_id: int
    corners_full: np.ndarray  # 4x2 float32 pixel coordinates in full sensor space
    centroid_full: tuple[float, float]
    x: float
    y: float

@dataclass
class ArucoDetectionResult:
    camera_id: str  # "left" or "right"
    frame_index: int
    timestamp_ns: int
    markers: list[ArUcoMarker2D]

@dataclass
class HandLandmark2D:
    landmark_id: int
    pixel_x_full: float
    pixel_y_full: float
    x: float
    y: float
    z: float
    visibility: float

@dataclass
class HandDetectionResult:
    camera_id: str  # "left" or "right"
    frame_index: int
    timestamp_ns: int
    landmarks: list[HandLandmark2D]
    handedness: list[dict[str, Any]]
    diagnostics: StereoDiagnostics
