# Evaluation of features/performance_optimization.md

## Overview
The proposed performance optimization plan addresses the correct bottlenecks (rendering latency and camera processing blocking the UI). However, the implementation details lack specific technical constraints required for a robust multi-threaded Python application, particularly regarding memory management and data synchronization.

## Critical Deficiencies

### 1. Missing Datatype Specifications
*   **Problem**: The `CameraPipeline.get_latest()` method returns a tuple `(frame, landmarks, fps)` without defining the specific types.
*   **Impact**:
    *   `landmarks`: This is a `mediapipe.python.solution_base.SolutionOutputs` object (specifically `multi_hand_landmarks`). This complex object is not a simple standard type. If the pipeline were to move to `multiprocessing` (to bypass GIL), this object might need serialization wrappers. For `threading`, it is fine, but type hinting should be explicit (`Any` or specific protocol) to avoid confusion.
    *   `frame`: Implicitly `np.ndarray`.
*   **Recommendation**: Explicitly document that `landmarks` is the raw MediaPipe result object and `frame` is a BGR `uint8` numpy array.

### 2. Thread Safety & Memory Management
*   **Problem**: The plan states: "Main Thread: `get_latest()` returns copy of `latest_data`."
*   **Impact**:
    *   **Buffer Reuse**: `cv2.VideoCapture.read()` and MediaPipe processing often involve internal buffer reuse. If the producer thread modifies the `frame` buffer while the main thread is rendering it (even if the *reference* was copied), tearing or artifacts will occur.
    *   **Cost of Copying**: A full deep copy of a 1080p frame (~6MB) is expensive (~1-3ms).
*   **Recommendation**:
    *   The producer thread must perform `frame.copy()` *before* releasing the lock/updating the shared variable if the underlying capture device reuses buffers.
    *   Alternatively, use a double-buffering scheme explicitly.

### 3. Synchronization & "New Data" Signal
*   **Problem**: The plan relies on checking "If `data` is new". It does not specify *how* to determine novelty.
*   **Impact**: Comparing large numpy arrays or complex MediaPipe objects for equality is computationally prohibitive and incorrect.
*   **Recommendation**: Add a `frame_id` (monotonic integer) or `timestamp` to the return tuple: `(frame_id, frame, landmarks, fps)`. The consumer can simply check `if new_id > last_processed_id`.

### 4. Dynamic Resolution Details
*   **Problem**: `src/light_map/svg_loader.py` currently returns a BGR image (`np.zeros(..., dtype=np.uint8)`). The plan mentions "Upscale result... using linear interpolation" but misses the alpha blending context.
*   **Impact**: If the map rendering is an overlay, it likely needs an Alpha channel (BGRA) or a mask. The current `render` method returns opaque BGR (black background). Upscaling a low-res opaque image and overlaying it might look blocky or obscure the camera feed if not handled with a proper transparency mask.
*   **Recommendation**:
    *   Specify `cv2.INTER_LINEAR` for the upscaling interpolation (fast and decent quality).
    *   Clarify if `svg_loader` should return BGRA or if the mask generation needs to be resolution-aware.

### 5. Caching Strategy
*   **Problem**: The caching mechanism for `render` suggests using `params` as a key.
*   **Impact**: Floating point parameters (`scale_factor`, `rotation`, `quality`) are notoriously bad hash keys due to precision issues.
*   **Recommendation**: Use `round(val, 4)` or similar quantization for cache keys to ensure cache hits. Specify an LRU cache size limit (e.g., `lru_cache(maxsize=32)`) to prevent OOM.

## Proposed Updates to Specification

### Updated `CameraPipeline` Interface
```python
@dataclass(frozen=True)
class VisionData:
    frame_id: int
    frame: np.ndarray  # BGR uint8
    landmarks: Any     # MediaPipe results
    fps: float

class CameraPipeline:
    def get_latest(self) -> Optional[VisionData]: ...
```

### Updated `svg_loader.render` Logic
*   **Input**: Add `quality: float` (quantized for caching).
*   **Output**: Ensure consistent channel count (BGR vs BGRA).
*   **Cache**: Use `functools.lru_cache` on a wrapper method that takes hashable arguments (tuples instead of lists, quantized floats).
