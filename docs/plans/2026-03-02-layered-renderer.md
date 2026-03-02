# Layered Composition Renderer Implementation Plan

> **For Gemini:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor the monolithic `Renderer` into a layered system using `ImagePatch` and `LayerMode` for better extensibility and performance. This plan also moves all secondary rendering logic (masking, overlays) into discrete layers.

**Architecture:** Transition from a single `render` method to a coordinator that composites `ImagePatch`es from a dynamic stack of `Layer` objects. Uses `WorldState` timestamps for granular caching.

**Tech Stack:** Python 3.12, OpenCV (cv2), NumPy.

______________________________________________________________________

### Task 1: Define Renderer Core Types (bd-28w)

**Files:**

- Modify: `src/light_map/common_types.py`
- Test: `tests/test_renderer_types.py`

**Step 1: Write the failing test**

```python
from light_map.common_types import ImagePatch, LayerMode
import numpy as np

def test_image_patch_creation():
    data = np.zeros((10, 10, 4), dtype=np.uint8)
    patch = ImagePatch(x=10, y=20, width=10, height=10, data=data)
    assert patch.x == 10
    assert patch.data.shape == (10, 10, 4)
```

**Step 2: Implement minimal types**

Add `LayerMode` (NORMAL, BLOCKING) and `ImagePatch` (x, y, w, h, data) to `common_types.py`.

______________________________________________________________________

### Task 2: Update WorldState with Component Timestamps (bd-1n8)

**Files:**

- Modify: `src/light_map/core/world_state.py`
- Test: `tests/test_world_state_timestamps.py`

**Requirement:** Every `apply` or `update` call must increment a monotonic timestamp if a change is detected.

**Timestamps to add:**

- `map_timestamp`, `menu_timestamp`, `tokens_timestamp`, `hands_timestamp`, `notifications_timestamp`, `viewport_timestamp`.

______________________________________________________________________

### Task 3: Refactor Renderer to Layered Coordinator (bd-i3y)

**Files:**

- Modify: `src/light_map/renderer.py`
- Test: `tests/test_renderer_layered.py`

**Requirement:** Implement the composition loop. Use an internal output buffer.
For `NORMAL` mode, use `numpy` for alpha blending:

```python
alpha = patch.data[:, :, 3:4] / 255.0
roi = buffer[y:y+h, x:x+w]
buffer[y:y+h, x:x+w] = (patch.data[:, :, :3] * alpha + roi * (1.0 - alpha)).astype(np.uint8)
```

______________________________________________________________________

### Task 4: Implement MapLayer (bd-1u9)

**Files:**

- Create: `src/light_map/map_layer.py`
- Test: `tests/test_map_layer.py`

**Logic:** Moves background map rendering and dimming logic. Uses `map_timestamp` and `viewport_timestamp` to invalidate its cache.

______________________________________________________________________

### Task 5: Implement MenuLayer (bd-1ru)

**Files:**

- Create: `src/light_map/menu_layer.py`
- Test: `tests/test_menu_layer.py`

**Logic:** Returns small `ImagePatch` objects for buttons and items. Uses `menu_timestamp`.

______________________________________________________________________

### Task 6: Implement SceneLayer wrapper (bd-1dy)

**Files:**

- Create: `src/light_map/scene_layer.py`
- Test: `tests/test_scene_layer.py`

**Logic:** Provides a clean buffer to `current_scene.render(frame)` and returns it as a full-screen `ImagePatch`. This allows legacy scenes to work within the new stack.

______________________________________________________________________

### Task 7: Implement HandMaskLayer (bd-2sq)

**Files:**

- Create: `src/light_map/hand_mask_layer.py`
- Test: `tests/test_hand_mask_layer.py`

**Logic:** Uses `hands_timestamp`. Produces `BLOCKING` patches for hand regions (blacked out) to prevent projection on hands.

______________________________________________________________________

### Task 8: Implement OverlayLayer (bd-23p)

**Files:**

- Create: `src/light_map/overlay_layer.py`
- Test: `tests/test_overlay_layer.py`

**Logic:** Handles global notifications, debug info, and token counts. Uses `notifications_timestamp` and `tokens_timestamp`.

______________________________________________________________________

### Task 9: Integrate Layered Renderer in InteractiveApp (bd-huf)

**Files:**

- Modify: `src/light_map/interactive_app.py`
- Test: `tests/test_interactive_app_layered.py`

**Requirement:** Initialize all layers and the stack in `InteractiveApp`. Replace the manual rendering sequence in `process_state` with a single `renderer.render(state, self.layer_stack)` call.

______________________________________________________________________

### Task 10: Cleanup Legacy Code and Methods (bd-3sy)

**Goal:** Remove monolithic rendering logic to prevent "dead code" accumulation.

**Steps:**

1. Remove `_apply_hand_masking` from `InteractiveApp`.
1. Remove `_render_base_layer` from `InteractiveApp`.
1. Remove `_render_global_overlays` from `InteractiveApp`.
1. Simplify the `Renderer` class by deleting its original `render()` method once the refactor is verified.
1. Verify all existing unit tests (`tests/test_renderer.py`, etc.) pass with the new architecture.
