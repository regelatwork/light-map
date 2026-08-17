# Sub-Design Specification: Dual Camera IPC & Shared Memory Manager

## 1. Overview & Objectives

This sub-design specifies the multi-process inter-process communication (IPC) and shared memory infrastructure for supporting dual camera capture streams in `light_map`.

The architecture isolates hardware frame capture into two dedicated producer processes (`CameraOperator(id="left")` and `CameraOperator(id="right")`), delivering zero-copy frame access to downstream detector processes while supporting **dynamic capture mode changes** (switching between full-frame 12MP calibration and high-speed cropped ROI sensor streams).

---

## 2. Multi-Process Topology & Supervision (`MultiCameraManager`)

```
                        ┌───────────────────────────────┐
                        │      MultiCameraManager       │
                        │    (Main Process Supervisor)  │
                        └───────┬───────────────┬───────┘
                                │               │
          Control Commands (L)  │               │ Control Commands (R)
         (CameraControlQueue)   │               │ (CameraControlQueue)
                                ▼               ▼
                  ┌───────────────────┐   ┌───────────────────┐
                  │ CameraOperator(L) │   │ CameraOperator(R) │
                  └─────────┬─────────┘   └─────────┬─────────┘
                            │ Writes                │ Writes
                            ▼                       ▼
                  ┌───────────────────┐   ┌───────────────────┐
                  │  shm_camera_left  │   │ shm_camera_right  │
                  └─────────┬─────────┘   └─────────┬─────────┘
                            │ Zero-Copy Views       │ Zero-Copy Views
                            ▼                       ▼
                  ┌───────────────────┐   ┌───────────────────┐
                  │ FrameProducer (L) │   │ FrameProducer (R) │
                  └───────────────────┘   └───────────────────┘
```

### 2.1 Process Supervisor Responsibilities & Memory Safety
To prevent shared memory leaks in `/dev/shm` on Raspberry Pi 5 if a child process crashes or receives `SIGKILL`:
1. `MultiCameraManager` (Main Process) creates all `multiprocessing.shared_memory.SharedMemory` segments (`shm_camera_left`, `shm_camera_right`).
2. Passes shared memory names to child processes (`CameraOperator` and `FrameProducer`).
3. Instantiates a **single shared `multiprocessing.Lock()`** per camera pipeline and passes it to both `CameraOperator` and `FrameProducer` to guarantee cross-process lock synchronization.
4. Registers robust cleanup (`atexit` & `SIGINT` signal handlers) so `shm.close()` and `shm.unlink()` are guaranteed to execute in the main process upon exit.

---

## 3. Shared Memory Layout & Dynamic Buffer Strategy

### 3.1 Max Payload Pre-Allocation
To support dynamic resolution switches (e.g. from $1920 \times 1080$ up to full 12MP $4608 \times 2592$) without reallocating OS shared memory segments during runtime:
* Each shared memory segment (`shm_camera_left` and `shm_camera_right`) is allocated to hold an $N+2$ ring buffer sized for the **maximum uncropped sensor payload** ($4608 \times 2592 \times 3 \text{ bytes} \approx 35.8\text{ MB}$ per slot).
* Ring buffer depth $N=3$ slots per camera stream.

### 3.2 Dynamic Frame Header Schema
Every buffer slot in shared memory begins with a 64-byte binary control header:

```python
# Shared Memory Slot Binary Header (Struct Format: '<qqiiiii')
header_struct = struct.Struct("<qqiiiii")

# Fields:
# 1. frame_index   (int64_t): Monotonic frame sequence counter
# 2. timestamp_ns  (int64_t): Hardware capture timestamp (time.monotonic_ns())
# 3. width         (int32_t): Active frame width in pixels (e.g. 1920 or 4608)
# 4. height        (int32_t): Active frame height in pixels (e.g. 1080 or 2592)
# 5. channels      (int32_t): Color channels (default: 3 for BGR)
# 6. roi_offset_x  (int32_t): Sensor crop horizontal offset in original sensor pixels
# 7. roi_offset_y  (int32_t): Sensor crop vertical offset in original sensor pixels
```

### 3.3 Zero-Copy Consumer View (`FrameProducer`)
When a consumer process calls `frame_producer.get_latest_frame()`:
1. Acquires the shared pipeline `mp.Lock()`.
2. Unpacks `frame_index`, `timestamp_ns`, `width`, `height`, `channels`, `roi_offset_x`, `roi_offset_y` from the 64-byte header.
3. Constructs a zero-copy numpy slice view over the active payload:
   ```python
   raw_bytes = shm.buf[slot_data_offset : slot_data_offset + (height * width * channels)]
   frame_view = np.ndarray((height, width, channels), dtype=np.uint8, buffer=raw_bytes)
   ```
4. Attaches metadata attributes (`frame_view.meta.roi_offset = (roi_offset_x, roi_offset_y)`).

---

## 4. Inbound Control Command Queue (`CameraControlQueue`)

Each `CameraOperator` checks its dedicated `CameraControlQueue` between frame capture loops.

### 4.1 Supported Control Commands

```python
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
```

### 4.2 Mode Transition & Crop Workflow
1. **Full-Resolution Capture Invariant:** Both cameras continuously capture at full sensor resolution (12MP mode) to maintain maximum pixel density for distant ArUco marker detection, with frame rate adapting naturally to hardware capability on Raspberry Pi 5.
2. **ROI Crop Stream:** During normal gameplay, `CameraOperator` applies the sensor ROI crop (`[crop_x, crop_y, crop_w, crop_h]`) to isolate the active table volume ($Z=0$ to $Z=200\text{mm}$), streaming only the cropped play area pixels into shared memory to eliminate unnecessary memory bandwidth.
3. **Calibration Reversion:** When entering the calibration wizard, `MultiCameraManager` sends `SetFullFrameCommand()`, directing `CameraOperator` to stream uncropped full-sensor frames until the active table bounding envelope is recalculated.
4. **Stream Pause during Transition:** When switching ROI modes, `CameraOperator` temporarily flags the stream status in shared memory as "transitioning", allowing `FrameProducer` to cleanly pause returning frames for 1–2 cycles without throwing exception errors.

---

## 5. Projection Model Coordinate Reconstruction

To map cropped sensor pixels back to the full camera intrinsics matrix $K$:
* Full-sensor pixel coordinates are reconstructed by adding the ROI offset:
  $$u_{\text{full}} = u_{\text{crop}} + \text{roi\_offset\_x}$$
  $$v_{\text{full}} = v_{\text{crop}} + \text{roi\_offset\_y}$$
* Alternatively, `CameraProjectionModel` adjusts optical centers dynamically:
  $$c_x' = c_x - \text{roi\_offset\_x}, \quad c_y' = c_y - \text{roi\_offset\_y}$$

This ensures 3D ray back-projection and stereo triangulation compute mathematically exact 3D coordinates from cropped frames without requiring lens re-calibration or causing distortion artifacts.

---

## 6. Verification Criteria

- [ ] `MultiCameraManager` creates shared memory segments in Main process and passes a single `mp.Lock()` per pipeline.
- [ ] Shared memory segments are unlinked (`shm.unlink()`) cleanly upon `Ctrl+C` / `SIGINT` without memory leaks.
- [ ] Frame headers store dynamic `width`, `height`, `roi_offset_x`, `roi_offset_y` accurately.
- [ ] `FrameProducer` creates valid zero-copy numpy views for both cropped and uncropped frames.
- [ ] Mode switching via `SetFullFrameCommand()` and `SetRoiCommand()` cleanly pauses frames during V4L2 transition without IPC crashes.
- [ ] Coordinate reconstruction ($u_{\text{full}} = u_{\text{crop}} + \text{roi\_offset\_x}$) produces identical 3D ray vectors for targets in cropped vs full-frame mode.
