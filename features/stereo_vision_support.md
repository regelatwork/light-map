# High-Level Design: Dual-Camera Stereographic Vision Support

## 1. Goal & Overview

This feature extends `light_map` from single-camera tracking to a **dual-camera stereographic vision architecture**. By combining feeds from two synchronized cameras, the system achieves two primary operational objectives:

1. **3D Occlusion Mitigation:** Eliminates line-of-sight occlusions caused by hands, physical terrain, and tall miniatures by maintaining continuous tracking when an object is visible in at least one camera view.
2. **True 3D Spatial Reconstruction:** Directly computes 3D coordinates $(X, Y, Z_{mm})$ for tokens, hands, and physical objects via stereo triangulation, eliminating reliance on single-camera parallax assumptions.

---

## 2. Hardware Topology & Assumptions

* **Sensors:** 2× Raspberry Pi Camera Module 3 devices.
* **Mounting:** Mounted on a rigid overhead frame looking down at the gaming table.
* **Baseline:** Fixed horizontal separation of approximately **128 mm**.
* **Field of View:** Significant FOV overlap covering the primary active projection area on the table.
* **Orientation & Role Auto-Discovery:** Left/Right physical device assignments (`/dev/video0` vs `/dev/video1`) and relative camera orientation are automatically detected during calibration, eliminating manual cable or index mapping.

---

## 3. Architecture & Data Flow

```
                     ┌───────────────────────┐       ┌───────────────────────┐
                     │ CameraOperator (Left) │       │ CameraOperator(Right) │
                     └───────────┬───────────┘       └───────────┬───────────┘
                                 │ Writes                        │ Writes
                                 ▼                               ▼
                     ┌───────────────────────┐       ┌───────────────────────┐
                     │   shm_camera_left     │       │   shm_camera_right    │
                     └───────────┬───────────┘       └───────────┬───────────┘
                                 │                               │
                ┌────────────────┴──────────────┐ ┌──────────────┴────────────────┐
                │ Reads latest frame            │ │ Reads latest frame            │
                ▼                               ▼ ▼                               ▼
┌───────────────────────────────┐ ┌───────────────────────────────┐ ┌───────────────────────────────┐
│  ArUcoDetectorProcess (Left)  │ │  ArUcoDetectorProcess (Right) │ │ HandDetectorProcess (L & R)   │
└───────────────┬───────────────┘ └───────────────┬───────────────┘ └───────────────┬───────────────┘
                │ Result(t_capture)               │ Result(t_capture)             │ Result(t_capture)
                └───────────────────────┬─────────┘                               │
                                        ▼                                         │
                        ┌───────────────────────────────┐                         │
                        │ Temporal Matching Aggregator  │◄────────────────────────┘
                        └───────────────┬───────────────┘
                                        │ Triangulated (X, Y, Z_mm)
                                        ▼
                        ┌───────────────────────────────┐
                        │          WorldState           │
                        └───────────────────────────────┘
```

---

## 4. Subsystem Detailed Designs

### 4.1 Frame Capture & Shared Memory IPC (`CameraOperator`)

* **Dual Capture Processes:** The system spawns two independent `CameraOperator` instances (`id="left"` and `id="right"`).
* **Zero-Copy Shared Memory:** Each process writes raw frames to a dedicated shared memory circular buffer (`shm_camera_left` and `shm_camera_right`) using an $N+2$ buffer strategy.
* **Timestamping:** Every written frame header includes an atomic `frame_index` and a precise hardware capture timestamp `t_capture = time.monotonic_ns()`.

### 4.2 Stereo Calibration & Auto-Role Discovery

* **Calibration Manifest (`stereo_calibration.json`):**
  * Intrinsics matrix $K$ and distortion coefficients $dist$ for Camera Left and Camera Right.
  * Extrinsics $(R_1, t_1)$ and $(R_2, t_2)$ relative to the tabletop coordinate system.
  * Relative rigid stereo transformation matrix $[R_{stereo} \mid T_{stereo}]$ between the two camera sensors.
* **Intrinsics Fallback Resolution:** To seamlessly support single-camera legacy setups and identical camera hardware (e.g. 2× RPi Cam 3), intrinsics are loaded via automatic fallback:
  * Camera Left: `camera_left_calibration.npz` $\to$ falls back to `camera_calibration.npz`.
  * Camera Right: `camera_right_calibration.npz` $\to$ falls back to `camera_calibration.npz`.
* **Token Heights from `tokens.json`:** During calibration, the wizard looks up physical token height $h_{mm}$ directly from `tokens.json` (`aruco_defaults` / `token_profiles`), ensuring exact SSOT alignment with configured token profiles.

* **Automatic Left/Right Identification:**
  During the calibration wizard, when both cameras view the shared calibration pattern on the table, the system calculates the relative horizontal translation vector $T_x$. The camera with positive $+T_x$ displacement is automatically registered as `camera_right` and the other as `camera_left`.


### 4.3 Asynchronous Time Synchronization & Adaptive Performance

To accommodate variable CPU load on embedded hardware (e.g. Raspberry Pi 5) where detection cadences adjust dynamically based on active workloads:

1. **Non-Backlogged Consumer Pull:** Detectors use `FrameProducer` to query `latest_index` from shared memory, dropping intermediate unprocessed frames to ensure zero processing backlog or result latency.
2. **Adaptive Temporal Matching Window ($\Delta t_{\text{match}}$):**
   Rather than using rigid time cutoffs, the aggregator continuously measures the rolling frame period ($\bar{T}_{\text{frame}}$) of the camera streams. To guarantee mutually exclusive 1-to-1 frame pairing without 1-to-many overlaps, the window is capped strictly below $0.5 \times \bar{T}_{\text{frame}}$:
   $$\Delta t_{\text{match}} = \min\left(0.4 \times \bar{T}_{\text{frame}},\; \text{max\_allowed\_skew}\right)$$
   *(e.g., if cameras run at 8 FPS / 125ms period, $\Delta t_{\text{match}} \approx 50\text{ms}$, accommodating non-genlocked clock drift on RPi 5 while strictly preventing duplicate frame pairing).*

3. **Adaptive Fallback Timeout:** If one detector drops a frame or experiences line-of-sight occlusion, the aggregator's fallback timeout adapts dynamically to the measured detector latency ($\bar{T}_{\text{detect}}$). After $\bar{T}_{\text{detect}} + 1.5 \sigma$, the available single-camera result is processed, intersecting the 3D ray with plane $Z = h_{\text{token}}$ (for tokens) or $Z_{\text{last\_known}}$ (for hands) to prevent position jumps.

### 4.4 3D Coordinate Schema in `WorldState`

Detections are represented in `WorldState` as Table-Relative 3D points $(X, Y, Z_{mm})$:
* **$X, Y$ (Tabletop Plane):** Map directly to table space in millimeters, used for map grid snapping, token placement, Fog of War, and distance calculations.
* **$Z_{mm}$ (Physical Elevation):** Represents height above the table surface ($Z=0$ is the tabletop). Allows measuring token height, stacked objects, hand/finger elevation, and 3D terrain blocks.

### 4.5 Typed Configuration & Web UI Integration

* **Pydantic Schema:** Introduce `CameraDeviceConfig` and `StereoVisionConfig` in `src/light_map/core/config_schema.py`.
* **TypeScript Auto-Generation:** Running `scripts/generate_ts_schema.py` produces typed interfaces for the React web interface, enabling real-time preview of Left/Right video streams and triggering stereo calibration wizards.

### 4.6 Auto-Calculated Sensor ROI & Digital Zoom (200mm Parallax Margin)

* **Calibration-Driven Sensor Crop:** To eliminate unnecessary memory bandwidth and CPU overhead from processing uncropped 12MP frames, calibration uses full-frame capture to detect the active table viewport.
* **Vertical Parallax Volume Envelope ($Z=200\text{mm}$):** Projects the 3D boundary envelope of the viewport from tabletop level ($Z=0\text{mm}$) up to maximum expected object height ($Z=200\text{mm}$).
* **Hardware Digital Zoom:** The combined bounding envelope (plus a 5% margin) is saved as `[crop_x, crop_y, crop_w, crop_h]` in `stereo_calibration.json`. The `CameraOperator` process applies this hardware crop via `libcamera`/V4L2 selection crop, streaming 1080p/1440p cropped frames to maximize capture efficiency and detector throughput on Raspberry Pi 5.

---

## 5. Implementation Roadmap (Sub-Designs)


The implementation of this feature will be broken down into the following targeted sub-design plans:

1. **Sub-Design 1: Stereo Calibration Wizard & Auto-Discovery** (`features/subdesigns/stereo_calibration_wizard.md`)
   * Calibration target detection, OpenCV `cv2.stereoCalibrate` integration, and automatic $+T_x$ Left/Right role assignment.
2. **Sub-Design 2: Dual Camera IPC & Shared Memory Manager** (`features/subdesigns/dual_camera_ipc.md`)
   * Multi-process spawning, dual `CameraOperator` management, shared memory buffer allocation, and cleanup.
3. **Sub-Design 3: Temporal Matching & 3D Triangulation Aggregator** (`features/subdesigns/stereo_triangulation_aggregator.md`)
   * Timestamp matching queue, $P_L/P_R$ matrix triangulation math, and non-blocking single-camera fallback logic.
4. **Sub-Design 4: ArUco & Hand Tracking Stereo Integration** (`features/subdesigns/stereo_detector_integration.md`)
   * Wiring ArUco token tracker and MediaPipe hand detector to the 3D stereo pipeline and updating `WorldState`.
5. **Sub-Design 5: Web UI & Backend API Integration** (`features/subdesigns/stereo_web_ui_integration.md`)
   * Pydantic schemas, API endpoints, TypeScript generation, dual-camera live preview, and React calibration wizard components.
6. **Sub-Design 6: Post-Implementation Cleanup & Refactoring Plan** (`features/subdesigns/stereo_cleanup_and_refactoring.md`)
   * AppContext refactoring, script updates, tokens.json scrubbing, test mock updates, and system documentation sync.



---

## 6. Verification Criteria

- [ ] Dual `CameraOperator` processes run concurrently without memory leaks or shared memory teardown issues.
- [ ] Stereo calibration wizard successfully identifies Left vs Right cameras based on $+T_x$ displacement.
- [ ] Triangulated 3D position of an ArUco marker matches physical measurement within $\pm 2.0\text{mm}$ error across tabletop area.
- [ ] When one camera is fully blocked by a hand, tracking seamlessly falls back to single-camera projection without dropping state.
- [ ] ArUco and Hand tracking run at their independent cadences without blocking the 30–60Hz main rendering loop.
