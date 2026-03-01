# Multiprocessing Refactor Implementation Plan

> **For Gemini:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor the Light Map application into a high-performance multi-process architecture using Shared Memory (N+2 Strategy) for zero-copy frame sharing and a reactive, event-driven main loop.

**Architecture:** A `CameraOperator` process acts as the producer, writing frames to Shared Memory. Multiple worker processes (`HandDetector`, `ArucoDetector`) consume frames via `FrameProducer` and push results to `multiprocessing.Queue`. The `MainLoopController` aggregates events, updates `WorldState` (with ROI extraction), and dispatches actions to scenes.

**Tech Stack:** Python `multiprocessing`, `multiprocessing.shared_memory`, `numpy` (views/sharing), `OpenCV` (ROI extraction/rendering).

---

### Task 1: Define IPC Types and DetectionResult

**Files:**
- Modify: `src/light_map/common_types.py`
- Test: `tests/test_common_types_ipc.py`

**Step 1: Write the failing test**

```python
from light_map.common_types import DetectionResult, ResultType, Action
import numpy as np

def test_detection_result_serialization():
    # Verify we can create and represent the new types
    res = DetectionResult(timestamp=123456, type=ResultType.ARUCO, data={"ids": [1]})
    assert res.timestamp == 123456
    assert res.type == ResultType.ARUCO
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_common_types_ipc.py`
Expected: FAIL (ImportError)

**Step 3: Write minimal implementation**

```python
# In src/light_map/common_types.py
class ResultType(StrEnum):
    ARUCO = "ARUCO"
    HANDS = "HANDS"
    GESTURE = "GESTURE"

class Action(StrEnum):
    SELECT = "SELECT"
    BACK = "BACK"
    MOVE = "MOVE"

@dataclass
class DetectionResult:
    timestamp: int
    type: ResultType
    data: Any
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_common_types_ipc.py`
Expected: PASS

**Step 5: Commit**

```bash
git add src/light_map/common_types.py tests/test_common_types_ipc.py
git commit -m "feat: add IPC and Action types to common_types"
```

---

### Task 2: Implement CameraOperator (The Producer)

**Files:**
- Create: `src/light_map/vision/camera_operator.py`
- Test: `tests/test_camera_operator.py`

**Step 1: Write the failing test**

```python
# test_camera_operator.py
# Verify it can write to shared memory
```

**Step 2: Run test to verify it fails**

**Step 3: Write minimal implementation**
Implement `CameraOperator` following `docs/plans/2026-03-01-multiprocessing-ipc-design.md`.
- Handles `multiprocessing.shared_memory` allocation.
- Implements `_write_frame(frame, timestamp)` with ref-count checking.

**Step 4: Run test to verify it passes**

**Step 5: Commit**

---

### Task 3: Implement FrameProducer (The Consumer)

**Files:**
- Create: `src/light_map/vision/frame_producer.py`
- Test: `tests/test_frame_producer.py`

**Step 1: Write the failing test**
Verify `get_latest_frame()` returns a view and `release()` decrements ref-count.

**Step 2: Run test to verify it fails**

**Step 3: Write minimal implementation**
Implement `FrameProducer` with `Acquire -> Process -> Release` logic.

**Step 4: Run test to verify it passes**

**Step 5: Commit**

---

### Task 4: Refactor WorldState with Functional Injection

**Files:**
- Modify: `src/light_map/core/app_context.py` (or where WorldState lives)
- Test: `tests/test_world_state_ipc.py`

**Step 1: Write the failing test**
Verify `update_from_frame(shm_view, timestamp)` calls the injected processor and copies ROI.

**Step 2: Run test to verify it fails**

**Step 3: Write minimal implementation**
- Add `frame_processor` to `__init__`.
- Implement `update_from_frame` and `apply(DetectionResult)`.
- Add granular `dirty_*` flags.

**Step 4: Run test to verify it passes**

**Step 5: Commit**

---

### Task 5: Implement VisionProcessManager (The Supervisor)

**Files:**
- Create: `src/light_map/vision/process_manager.py`
- Test: `tests/test_process_manager.py`

**Step 1: Write the failing test**
Verify `start()` spawns processes and `stop()` calls `unlink()`.

**Step 2: Run test to verify it fails**

**Step 3: Write minimal implementation**
Implement `VisionProcessManager` with process health monitoring and cleanup.

**Step 4: Run test to verify it passes**

**Step 5: Commit**

---

### Task 6: Refactor InputManager for Action Mapping

**Files:**
- Modify: `src/light_map/input_manager.py`
- Test: `tests/test_input_manager_actions.py`

**Step 1: Write the failing test**
Verify `get_actions()` returns semantic actions from combined hardware/gesture inputs.

**Step 2: Run test to verify it fails**

**Step 3: Write minimal implementation**
- Add `cv2.waitKey` polling.
- Add gesture polling from `WorldState`.
- Map to `Action` enum.

**Step 4: Run test to verify it passes**

**Step 5: Commit**

---

### Task 7: Implement MainLoopController and Integration

**Files:**
- Create: `src/light_map/core/main_loop.py`
- Modify: `src/light_map/interactive_app.py`
- Test: `tests/test_main_loop_integration.py`

**Step 1: Write the failing test**
End-to-end test with mocked shared memory and detectors.

**Step 2: Run test to verify it fails**

**Step 3: Write minimal implementation**
Implement the high-frequency polling loop aggregating queues, updating state, and triggering render.

**Step 4: Run test to verify it passes**

**Step 5: Commit**

---

### Task 8: Cleanup and Latency Verification

**Step 1: Implement latency instrumentation**
Add timestamps to the render output and verify "Glass-to-Glass" latency.

**Step 2: Run final verification suite**

**Step 3: Commit and Close Epic**
