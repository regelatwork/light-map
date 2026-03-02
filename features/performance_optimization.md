# Feature: Performance Optimization

## Problem Analysis

- **Baseline Latency**: ~70-80ms per frame (limited by AI/Camera).
- **Rendering Latency**: Spikes to 800ms+ with complex maps.
- **Total FPS**: ~1 FPS (Map) vs ~13 FPS (No Map).

## Goals

1. **Eliminate Rendering Bottleneck**: Reduce map rendering time during interaction to \<50ms.
1. **Maximize Throughput**: Decouple camera/AI processing from rendering to achieve higher frame rates.

## Phase 1: Dynamic Resolution Rendering (Immediate Fix)

### Concept

Use a "Level of Detail" approach where the map renders at lower resolution during interaction (Pan/Zoom) and snaps to full resolution when static.

### Implementation Details

#### 1. `src/light_map/svg_loader.py`

- **Modifications**: Update `render` method with caching and quality scaling.
- **Interface Change**:
  ```python
  def render(
      self,
      width: int,
      height: int,
      scale_factor: float = 1.0,
      offset_x: int = 0,
      offset_y: int = 0,
      rotation: float = 0.0,
      quality: float = 1.0,  # NEW: 0.1 to 1.0
  ) -> np.ndarray:
  ```
- **Logic**:
  - **Caching Strategy**: Use `functools.lru_cache(maxsize=32)`. To ensure cache hits, internal logic should wrap arguments in a hashable format (e.g., tuples) and **quantize float parameters** (e.g., `round(val, 4)`).
  - If `quality < 1.0`:
    - Create internal buffer of size `(w*quality, h*quality)`.
    - Scale `vp_matrix` by `quality`.
    - Render SVG to internal buffer.
    - Upscale result to `(width, height)` using **`cv2.INTER_LINEAR`**.
  - **Return Type**: Returns `np.ndarray` (BGR, uint8). If transparency is needed later, switch to BGRA, but current implementation assumes BGR.

#### 2. `src/light_map/interactive_app.py`

- **Modifications**: `process_frame`.
- **Logic**:
  - Detect interaction state (Panning/Zooming).
  - If interacting, call `svg_loader.render(..., quality=0.25)`.
  - If static (no interaction for > N frames), call `svg_loader.render(..., quality=1.0)`.

#### 3. Tests (`tests/test_svg_loader.py`)

- **Test Case 1: Resolution Scaling**:
  - Call `render(100, 100, quality=0.5)`.
  - Verify internal logic or visual output dimensions/speed.
- **Test Case 2: Caching**:
  - Call `render(...)` twice with same params.
  - Verify identity of returned object.

## Phase 2: Pipeline Instrumentation and Multi-Process Refactor

The system has been refactored from a threaded architecture to a **Multi-Process Architecture** to fully utilize multi-core CPUs and bypass the Python GIL. This refactor is documented in [Multiprocessing Architecture](../docs/multiprocessing.md).

To ensure visibility into system bottlenecks, we have implemented **Pipeline Instrumentation** to track "hop" latencies and resource contention. See [Performance Instrumentation](../docs/performance_instrumentation.md) for details on how we measure and optimize end-to-end performance.
