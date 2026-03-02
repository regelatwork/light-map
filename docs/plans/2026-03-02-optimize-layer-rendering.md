# Layer Rendering Optimization Implementation Plan

> **For Gemini:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement change detection and intermediate caching in the `Renderer` and `Layer` architecture to minimize CPU/GPU usage by skipping redundant composition and SVG rendering.

**Architecture:**

1. **State-Aware Layers:** Update `Layer` base class to manage caching and `is_dirty` logic internally, using `is_static` to identify background components.
1. **Renderer Caching:** The `Renderer` will maintain a `background_cache` for static layers and skip the entire process if no layers are dirty.
1. **Refactored Layers:** Update all existing layers to conform to the new `Layer` interface.

**Tech Stack:** Python 3.12, OpenCV (cv2), NumPy.

______________________________________________________________________

### Task 1: Update Layer Base Class

**Files:**

- Modify: `src/light_map/common_types.py`
- Test: `tests/test_renderer_types.py`

**Step 1: Write the failing test for Layer dirty logic**

```python
from light_map.common_types import Layer, ImagePatch, LayerMode
from light_map.core.world_state import WorldState
from typing import List
import numpy as np

class MockLayer(Layer):
    def __init__(self, state, is_static=False):
        super().__init__(state=state, is_static=is_static)
        self.generate_count = 0
    
    @property
    def is_dirty(self) -> bool:
        return self.state.map_timestamp > self._last_state_timestamp
    
    def _generate_patches(self) -> List[ImagePatch]:
        self.generate_count += 1
        return [ImagePatch(0, 0, 10, 10, np.zeros((10, 10, 4), dtype=np.uint8))]

def test_layer_caching():
    state = WorldState()
    layer = MockLayer(state)
    
    # First render
    patches = layer.render()
    assert layer.generate_count == 1
    
    # Second render without change
    patches = layer.render()
    assert layer.generate_count == 1
    
    # Change state
    state.increment_map_timestamp()
    patches = layer.render()
    assert layer.generate_count == 2
```

**Step 2: Update Layer definition in `common_types.py`**

```python
class Layer(ABC):
    """Abstract Base Class for all visual layers."""

    def __init__(
        self,
        state: Optional[WorldState] = None,
        is_static: bool = False,
        mode: LayerMode = LayerMode.NORMAL,
    ):
        self.state = state
        self.is_static = is_static
        self.layer_mode = mode
        self._cached_patches: List[ImagePatch] = []
        self._last_state_timestamp: int = -1

    @property
    @abstractmethod
    def is_dirty(self) -> bool:
        """True if the layer needs to re-render its patches."""
        pass

    def render(self) -> List[ImagePatch]:
        """Handles caching and calls _generate_patches if dirty."""
        if self.is_dirty or not self._cached_patches:
            self._cached_patches = self._generate_patches()
            self._update_timestamp()
        return self._cached_patches

    def _update_timestamp(self):
        """Internal helper to sync timestamp after render."""
        # This is a bit tricky as different layers use different timestamps.
        # We'll let subclasses override this or just use a generic 'last_rendered'
        pass

    @abstractmethod
    def _generate_patches(self) -> List[ImagePatch]:
        """Actual rendering logic implemented by subclasses."""
        pass
```

**Step 3: Run tests**
Run: `pytest tests/test_renderer_types.py`

**Step 4: Commit**
`git add src/light_map/common_types.py && git commit -m "feat: update Layer base class for optimization"`

______________________________________________________________________

### Task 2: Implement Renderer Background Caching

**Files:**

- Modify: `src/light_map/renderer.py`
- Test: `tests/test_renderer_layered.py`

**Step 1: Write failing test for Renderer skip logic**

```python
def test_renderer_skip_if_not_dirty():
    renderer = Renderer(100, 100)
    state = WorldState()
    layer = MockLayer(state)
    
    # Initial render
    frame = renderer.render(state, [layer])
    assert frame is not None
    
    # Subsequent render without changes should return None
    frame = renderer.render(state, [layer])
    assert frame is None
```

**Step 2: Update Renderer implementation**

- Add `background_cache`.
- Implement static flattening logic.
- Use `np.copyto` for efficiency.

**Step 3: Run tests**
Run: `pytest tests/test_renderer_layered.py`

**Step 4: Commit**
`git add src/light_map/renderer.py && git commit -m "feat: implement Renderer background caching and skip logic"`

______________________________________________________________________

### Task 3: Update MapLayer

**Files:**

- Modify: `src/light_map/map_layer.py`
- Test: `tests/test_map_layer.py`

**Step 1: Refactor MapLayer to use new Layer interface**

- `is_static = True`.
- Implement `is_dirty` using `state.map_timestamp` and `state.viewport_timestamp`.
- Move logic to `_generate_patches`.

**Step 2: Verify and Commit**

______________________________________________________________________

### Task 4: Update MenuLayer

**Files:**

- Modify: `src/light_map/menu_layer.py`
- Test: `tests/test_menu_layer.py`

**Step 1: Refactor MenuLayer**

- `is_static = False`.
- Implement `is_dirty` using `state.menu_timestamp`.

**Step 2: Verify and Commit**

______________________________________________________________________

### Task 5: Update HandMaskLayer

**Files:**

- Modify: `src/light_map/hand_mask_layer.py`
- Test: `tests/test_hand_mask_layer.py`

**Step 1: Refactor HandMaskLayer**

- `is_static = False`.
- Implement `is_dirty` using `state.hands_timestamp`.

**Step 2: Verify and Commit**

______________________________________________________________________

### Task 6: Update OverlayLayer

**Files:**

- Modify: `src/light_map/overlay_layer.py`
- Test: `tests/test_overlay_layer.py`

**Step 1: Refactor OverlayLayer**

- `is_static = False`.
- Implement `is_dirty` using `state.notifications_timestamp` and `state.tokens_timestamp`.

**Step 2: Verify and Commit**

______________________________________________________________________

### Task 7: Update SceneLayer

**Files:**

- Modify: `src/light_map/scene_layer.py`
- Test: `tests/test_scene_layer.py`

**Step 1: Refactor SceneLayer**

- `is_static = True` (usually, but maybe configurable).
- Implement `is_dirty` using `state.scene_timestamp`.

**Step 2: Verify and Commit**

______________________________________________________________________

### Task 8: Final Integration and Performance Verification

**Goal:** Ensure `InteractiveApp` still works and measure if skipping happens correctly.

**Steps:**

1. Run all tests.
1. Verify in `InteractiveApp` that `renderer.render` returns `None` during idle.
