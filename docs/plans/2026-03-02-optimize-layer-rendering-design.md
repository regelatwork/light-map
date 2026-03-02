# Layer Rendering Optimization Design

**Date:** 2026-03-02
**Status:** Validated
**Epic:** bd-6i2 (Refactor Renderer into a Layered Composition System)

## Goal
The goal of this design is to optimize the `Renderer` and `Layer` architecture to minimize CPU and GPU usage. By implementing change detection and intermediate caching, the system will avoid redundant SVG rendering and skip the entire composition pipeline when no state changes are detected.

## Architecture

### 1. State-Aware Layers
The `Layer` base class is updated to support optional `WorldState` injection and standardized change detection.

- **Constructor Injection:** `Layer(state: Optional[WorldState] = None, is_static: bool = False)`
- **`is_dirty` Property:** Concrete layers implement this to check `WorldState` timestamps (e.g., `state.map_timestamp`) or internal flags (e.g., `opacity` changes).
- **`is_static` Property:** Indicates if a layer belongs to the "Static Background" group (rarely changes) or the "Dynamic Overlay" group (changes frequently).

### 2. Intermediate Caching (Renderer)
The `Renderer` optimizes composition by maintaining an intermediate buffer for static content.

- **`background_cache`:** A full-screen buffer storing the flattened result of all layers marked `is_static=True` (e.g., `MapLayer`, `SceneLayer`).
- **Cache Invalidation:** The `background_cache` is only updated if one or more static layers report `is_dirty=True`.
- **Composition Loop:**
    1. If no layers are dirty, `render()` returns `None`.
    2. If static layers are dirty, update `background_cache`.
    3. Copy `background_cache` to `output_buffer`.
    4. Blend dynamic layers (e.g., `HandMaskLayer`, `MenuLayer`) on top of `output_buffer`.

## Component Details

### Layer Base Class (`src/light_map/common_types.py`)
```python
class Layer(ABC):
    def __init__(self, state: Optional[WorldState] = None, is_static: bool = False, mode: LayerMode = LayerMode.NORMAL):
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

    @abstractmethod
    def _generate_patches(self) -> List[ImagePatch]:
        """Actual rendering logic implemented by subclasses."""
        pass
```

### Renderer (`src/light_map/renderer.py`)
- Maintains `background_cache` (RGB) and `output_buffer` (RGB).
- Uses `np.copyto` for fast buffer initialization from cache.
- Skips processing entirely if no layers are dirty.

## Data Flow
1. **Change Detection:** `WorldState` increments granular timestamps (e.g., `tokens_timestamp`) when new vision results or inputs are applied.
2. **Dirty Check:** `Renderer.render()` polls all layers in the stack for their `is_dirty` status.
3. **Static Flattening:** If any static layer is dirty, the `Renderer` clears and re-composites all static layers into the `background_cache`.
4. **Dynamic Blending:** `Renderer` copies `background_cache` to `output_buffer` and blends dynamic layer patches.
5. **Idle State:** If no changes occur, the `InteractiveApp` receives `None` and skips the hardware display update.

## Testing Strategy
- **Unit Tests:** Verify `is_dirty` logic for each layer type (Map, Menu, HandMask).
- **Regression Tests:** Ensure `Renderer` still produces correct pixel-perfect output compared to the monolithic version.
- **Performance Benchmarks:** Measure CPU usage during idle (no movement) vs. active (hand tracking) states.
