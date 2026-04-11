# Plan: Refactor Rendering to a Purely Data-Driven and Hierarchical Architecture

This plan describes the elimination of the "dynamic rendering" anti-pattern and the introduction of `CompositeLayer` to optimize the system using state-driven versioning throughout.

## Objective

1. **Eliminate the `is_dynamic` flag:** Rendering must be purely reactive to state changes. If a visual needs to update, its underlying data in `WorldState` must update its version.
1. **Introduce `CompositeLayer`:** Provide a way to flatten sub-stacks of layers into a single cached patch to optimize the main renderer's compositing loop.
1. **Simplify `Renderer`:** Move the responsibility for intermediate caching into the layers themselves, making the top-level renderer a simple compositor of patches.

## Core Problem

Currently, several layers and scenes use an `is_dynamic` flag to force re-rendering every frame. This bypasses the versioning system, making it harder to reason about performance and state synchronization. Furthermore, the `Renderer` has a "one-level" background cache that is hardcoded to use the `is_static` property, which is inflexible.

## Detailed Changes

### 1. `src/light_map/common_types.py`

- **Modify `Layer` base class:**
  - Remove `self._is_dynamic: bool = False` from `__init__`.
  - Remove the `self._is_dynamic` check from `render()`.
- **Implement `CompositeLayer(Layer)`:**
  - `__init__(self, state, layers: List[Layer], is_static: bool = True)`
  - `get_current_version()`: Returns a hash or sum of all internal layers' versions.
  - `_generate_patches()`:
    1. Create a transparent RGBA buffer.
    1. Call `render()` on each internal layer.
    1. Composite all patches into the buffer.
    1. Return a single `ImagePatch` covering the whole buffer.
  - **Optimization:** If all internal layers return empty patches, return an empty list.

### 2. `src/light_map/core/world_state.py`

- **Data-Driven FPS:**
  - Wrap `fps` in a `VersionedAtom`.
  - Rename `update_performance_metrics` to `update_fps` and let it update the atom.
- **Ensure animation states are atoms:**
  - `dwell_state` and `summon_progress` are already atoms.
  - Verify other scenes (like calibration) use atoms for their "stages" or progress.

### 3. `src/light_map/renderer.py`

- **Simplify `render()`:**
  - Remove the `getattr(layer, "_is_dynamic", False)` check.
  - Remove the special `background_cache` and `current_background_version` logic.
  - The new `render()` will:
    1. Check if any layer version changed or if the stack changed.
    1. If so, iterate through *all* layers.
    1. Call `layer.render(current_time)`.
    1. Composite all patches onto the output buffer.
  - **Note:** Caching now happens at the layer level (individual layers or `CompositeLayer`).

### 4. `src/light_map/core/scene.py`

- Remove `self.is_dynamic: bool = False` from the base `Scene` class.

### 5. `src/light_map/scene_layer.py`

- Update `get_current_version()` to remove the check for `self.scene.is_dynamic` and `system_time_version`.
- If a scene is animating, it should update its `scene_state` atom in `WorldState`.

### 6. Update Calibration and Other Scenes

- **`src/light_map/scenes/calibration_scenes.py`**:
  - Remove `self.is_dynamic = True`.
  - Ensure every state change (e.g. `self._stage = ...`) updates the `scene_state` in `WorldState`.
- **`src/light_map/overlay_layer.py`**:
  - Update `DebugLayer` to remove `_is_dynamic` and rely on `hands_version` and the new `fps_version`.

## Verification Plan

### Automated Tests

- `pytest tests/test_renderer.py` (Verify it still skips rendering when no versions change).
- `pytest tests/test_world_state_invariants.py` (Verify `fps_version` behaves as expected).
- Create `tests/test_composite_layer.py` to verify flattening logic.

### Manual Verification

- Run the app in debug mode. Verify the FPS and landmarks still update (they should, as long as `hands_version` or `fps_version` increments).
- Enter a calibration scene. Verify it still progresses through stages correctly.

## Migration Guide for Junior Developers

- **The "Static" Rule:** Every visual element must be tied to a data version. If you want something to move or pulse, you must update its state in `WorldState` (e.g., a progress float or a state enum).
- **Composite for Speed:** If you have multiple layers that change together or not at all (e.g., Map and its Overlays), wrap them in a `CompositeLayer`. This helps the renderer stay fast by reducing the number of compositing steps.
