# Sub-Design Specification: ArUco & Hand Tracking Stereo Integration

## 1. Overview & Objectives

This sub-design specifies the integration of ArUco token tracking and MediaPipe hand tracking detector processes into the dual-camera 3D stereographic architecture for `light_map`.

It details worker process dispatching, IPC message schemas, `WorldState` 3D coordinate storage, rendering layer updates (`ArucoMaskLayer`, `Projector3DLayer`), and Web UI diagnostic synchronization.

______________________________________________________________________

## 2. Detector Process Architecture & Result Schemas

```
                 ┌──────────────────────────────────────────────────┐
                 │                Detector Processes                │
                 ├────────────────────────┬─────────────────────────┤
                 │ Left Camera Stream     │ Right Camera Stream     │
                 ├────────────────────────┼─────────────────────────┤
                 │ ArucoDetectorProcess(L)│ ArucoDetectorProcess(R) │
                 │ HandDetectorProcess(L) │ HandDetectorProcess(R)  │
                 └───────────┬────────────┴────────────┬────────────┘
                             │ Bounded IPC Queues (maxsize=2)
                             ▼                         ▼
                 ┌──────────────────────────────────────────────────┐
                 │          TrackingCoordinator (Main)             │
                 │      (Temporal Matching & Triangulation)         │
                 └────────────────────────┬─────────────────────────┘
                                          │ Updates
                                          ▼
                 ┌──────────────────────────────────────────────────┐
                 │                    WorldState                    │
                 └──────────────────────────────────────────────────┘
```

### 2.1 Outbound Result Message Schemas & Queue Bounding

To prevent memory buildup and pipeline congestion on Raspberry Pi 5:

- Outbound result queues use a strict `maxsize = 2` slots with `queue.put_nowait()`. If the main process coordinator is busy, stale detection results are automatically dropped.
- Detector processes add `roi_offset` to 2D centroids before emitting result messages, delivering full-sensor uncropped pixel coordinates to `TrackingCoordinator`.

```python
@dataclass
class ArUcoMarker2D:
    marker_id: int
    corners_full: np.ndarray  # 4x2 float32 pixel coordinates in full sensor space
    centroid_full: tuple[float, float]


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
    visibility: float


@dataclass
class HandDetectionResult:
    camera_id: str  # "left" or "right"
    frame_index: int
    timestamp_ns: int
    landmarks: list[HandLandmark2D]
```

______________________________________________________________________

## 3. `WorldState` 3D Data Structures & Diagnostics

The `TrackingCoordinator` updates `WorldState` with triangulated 3D spatial representations following the strict Writer Token pattern:

### 3.1 3D Token State (`WorldState.tokens`)

```python
@dataclass
class Token3DState:
    id: str
    name: str
    type: str  # "PC" or "NPC"
    grid_x: float
    grid_y: float
    world_x: float  # Tabletop X in mm
    world_y: float  # Tabletop Y in mm
    world_z: float  # Elevation height in mm
    is_stereo_triangulated: bool
    last_seen_ns: int
```

### 3.2 Stereo Diagnostics (`WorldState.diagnostics`)

```python
@dataclass
class StereoDiagnostics:
    left_camera_fps: float
    right_camera_fps: float
    stereo_match_ratio: float  # Percentage of matched stereo pairs vs single-cam fallbacks
    active_mode: str  # "FULL_FRAME" vs "HIGH_SPEED_ROI"
```

______________________________________________________________________

## 4. Rendering Layer & Web UI Integration

### 4.1 `ArucoMaskLayer` Polygon Projection

- Uses $(world_x, world_y)$ base coordinates and height $world_z$ to project a 4-corner padded convex polygon over physical tokens, preventing projector light from blinding player tokens.
- Using actual triangulated base coordinates eliminates parallax mask shift.

### 4.2 `Projector3DLayer` AR Graphics

- Uses `projection_service.project_3d_to_projector()` to render 3D-aware graphics (e.g. selection rings, health badges, condition labels) attached directly to token tops at $Z = world_z$.

### 4.3 Web UI Diagnostic Dashboard

React web control interface subscribes to `WorldState.diagnostics` to display live performance metrics:

- Left/Right Camera FPS indicators.
- Stereo Match Ratio indicator.
- Active Capture Mode indicator (`FULL_FRAME` vs `HIGH_SPEED_ROI`).

______________________________________________________________________

## 5. Verification Criteria

- [ ] Outbound IPC queues use `maxsize=2` with non-blocking put to prevent queue congestion on RPi 5.
- [ ] 2D centroids include `roi_offset` reconstruction before entering result queues.
- [ ] `WorldState.tokens` updates with valid 3D coordinates $(world_x, world_y, world_z)$ and `is_stereo_triangulated` flag.
- [ ] `WorldState.diagnostics` stores live Left/Right camera FPS and stereo match ratio.
- [ ] Projector light masks (`ArucoMaskLayer`) project accurate 4-corner padded polygons centered over physical tokens.
