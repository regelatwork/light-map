# Layered Composition Renderer Implementation Plan

> **For Gemini:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor the monolithic `Renderer` into a layered system using `ImagePatch` and `LayerMode` for better extensibility and performance.

**Architecture:** Transition from a single `render` method to a coordinator that composites `ImagePatch`es from a dynamic stack of `Layer` objects. Uses `WorldState` timestamps for granular caching.

**Tech Stack:** Python 3.12, OpenCV (cv2), NumPy.

---

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

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_renderer_types.py -v`
Expected: FAIL (ImportError)

**Step 3: Write minimal implementation**

```python
from enum import Enum, auto
from dataclasses import dataclass

class LayerMode(Enum):
    NORMAL = auto()
    BLOCKING = auto()

@dataclass
class ImagePatch:
    x: int
    y: int
    width: int
    height: int
    data: np.ndarray # RGBA
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_renderer_types.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/light_map/common_types.py tests/test_renderer_types.py
git commit -m "feat: add Renderer core types ImagePatch and LayerMode"
br update bd-28w --status=closed
```

---

### Task 2: Update WorldState with Component Timestamps (bd-1n8)

**Files:**
- Modify: `src/light_map/core/world_state.py`
- Test: `tests/test_world_state_timestamps.py`

**Step 1: Write the failing test**

```python
from light_map.core.world_state import WorldState

def test_world_state_timestamps():
    ws = WorldState()
    assert hasattr(ws, 'map_timestamp')
    assert ws.map_timestamp == 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_world_state_timestamps.py -v`
Expected: FAIL (AttributeError)

**Step 3: Write minimal implementation**

Add `map_timestamp`, `menu_timestamp`, etc., to `__init__` and update them in relevant update methods.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_world_state_timestamps.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/light_map/core/world_state.py tests/test_world_state_timestamps.py
git commit -m "feat: add component timestamps to WorldState"
br update bd-1n8 --status=closed
```

---

### Task 3: Refactor Renderer to Layered Coordinator (bd-i3y)

**Files:**
- Modify: `src/light_map/renderer.py`
- Test: `tests/test_renderer_layered.py`

**Step 1: Write the failing test**

Test the composition logic with mock layers.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_renderer_layered.py -v`

**Step 3: Write minimal implementation**

Implement the `Renderer.render(state, layers)` loop.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_renderer_layered.py -v`

**Step 5: Commit**

```bash
git add src/light_map/renderer.py tests/test_renderer_layered.py
git commit -m "refactor: transition Renderer to layered composition"
br update bd-i3y --status=closed
```

---

### Task 4: Implement MapLayer (bd-1u9)

**Files:**
- Create: `src/light_map/map_layer.py`
- Test: `tests/test_map_layer.py`

**Step 1: Write the failing test**

Verify `MapLayer` returns an `ImagePatch` covering the screen with background data.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_map_layer.py -v`

**Step 3: Write minimal implementation**

Implement `MapLayer.render` by moving background/map dimming logic from `Renderer`.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_map_layer.py -v`

**Step 5: Commit**

```bash
git add src/light_map/map_layer.py tests/test_map_layer.py
git commit -m "feat: implement MapLayer"
br update bd-1u9 --status=closed
```

---

### Task 5: Implement MenuLayer (bd-1ru)

**Files:**
- Create: `src/light_map/menu_layer.py`
- Test: `tests/test_menu_layer.py`

**Step 1: Write the failing test**

Verify `MenuLayer` returns `ImagePatch` objects for each active menu item.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_menu_layer.py -v`

**Step 3: Write minimal implementation**

Implement `MenuLayer.render` by moving menu drawing logic from `Renderer`.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_menu_layer.py -v`

**Step 5: Commit**

```bash
git add src/light_map/menu_layer.py tests/test_menu_layer.py
git commit -m "feat: implement MenuLayer"
br update bd-1ru --status=closed
```

---

### Task 6: Integrate Layered Renderer in InteractiveApp (bd-huf)

**Files:**
- Modify: `src/light_map/interactive_app.py`
- Test: `tests/test_interactive_app_layered.py`

**Step 1: Write the failing test**

Verify `InteractiveApp` uses the new `Renderer` and layers stack.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_interactive_app_layered.py -v`

**Step 3: Write minimal implementation**

Initialize `Renderer`, `MapLayer`, and `MenuLayer` in `InteractiveApp` and update the `draw` method.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_interactive_app_layered.py -v`

**Step 5: Commit**

```bash
git add src/light_map/interactive_app.py tests/test_interactive_app_layered.py
git commit -m "feat: integrate layered renderer in InteractiveApp"
br update bd-huf --status=closed
br sync --flush-only
```

