# Optimization of Rendering Performance Implementation Plan

> **For Gemini:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce rendering latency from ~200ms to <50ms by refactoring layers to be fully reactive (fixing app invariants) and utilizing `CompositeLayer` with optimized `MASKED` composition.

**Architecture:** 
1. **Reactive Layer Refactor (FIX):** Modify `FogOfWarLayer`, `VisibilityLayer`, and `DoorLayer` to pull all data (masks, blockers, grid info) from `WorldState` atoms rather than external managers. 
2. **Stable Layer Lifecycle:** Remove re-instantiation logic in `LayerStackManager`. Layers are created once, ensuring stable object identities for the `Renderer` and `CompositeLayer`.
3. **New Layer Mode:** Add `LayerMode.MASKED` for binary masks (0 or 255) to enable a high-performance composition fast-path.
4. **Shared Composition Utility:** Extract the composition logic (including `MASKED` indexing and `NORMAL` alpha blending) to a shared utility used by both `Renderer` and `CompositeLayer`.
5. **Versioning Refinement:** Stabilize `HandMaskLayer` and `ArucoMaskLayer` versioning to prevent unnecessary foreground re-composition.

**Tech Stack:** Python, NumPy, OpenCV (cv2)

---

### Task 1: Protocol Update and Shared Composition Utility

**Files:**
- Modify: `src/light_map/state/world_state.py`
- Modify: `src/light_map/core/common_types.py`
- Create: `src/light_map/rendering/composition_utils.py`
- Test: `tests/test_composite_layer.py`

**Step 1: Add fow_disabled atom to WorldState**
Add `_fow_disabled_atom` (bool) and its corresponding property to `WorldState`.

**Step 2: Add LayerMode.MASKED and refactor CompositeLayer**
- Add `MASKED = "MASKED"` to the `LayerMode` enum in `common_types.py`.
- Update `CompositeLayer.get_current_version` to use `max()` of child versions.

**Step 3: Create Shared Composition Utility**
Create `src/light_map/rendering/composition_utils.py`:
```python
def composite_patch(buffer, patch, mode, screen_width, screen_height):
    # ... logic for BLOCKING, NORMAL, and MASKED ...
    # Use cv2.addWeighted for constant-alpha optimization in NORMAL mode
```

**Step 4: Refactor Renderer and CompositeLayer to use the utility**
Replace internal composition logic in both classes with a call to the new utility.

**Step 5: Verify with tests**
Create `tests/test_composite_layer.py` to verify caching and versioning logic.

---

### Task 2: Reactive Layer Refactor

**Files:**
- Modify: `src/light_map/rendering/layers/fow_layer.py`
- Modify: `src/light_map/rendering/layers/visibility_layer.py`
- Modify: `src/light_map/rendering/layers/door_layer.py`

**Step 1: Refactor FogOfWarLayer**
- Remove `FogOfWarManager` and `grid_spacing/origin` from `__init__`.
- In `_generate_patches`, use `self.state.fow_mask`, `self.state.fow_disabled`, and `self.state.grid_metadata`.
- Set `self.layer_mode = LayerMode.MASKED`.

**Step 2: Refactor VisibilityLayer**
- Remove dependency on manager width/height and grid info in `__init__`.
- In `_generate_patches`, pull all parameters from `self.state`.

**Step 3: Refactor DoorLayer**
- Pull `blockers` from `self.state.blockers`. 
- **Important:** Access blocker data via dictionary keys (e.g., `b['is_open']`) instead of object attributes.

---

### Task 3: Stabilize LayerStackManager

**Files:**
- Modify: `src/light_map/core/layer_stack_manager.py`

**Step 1: Remove re-instantiation logic**
Empty `update_visibility_stack`. The layers are now reactive.

**Step 2: Initialize Background Composite once**
In `__init__`, create `self.background_composite = CompositeLayer([self.map_layer, self.door_layer, self.fow_layer, self.visibility_layer])`.

**Step 3: Update stack property**
Ensure `layer_stack` returns the `background_composite` as its first element.

---

### Task 4: Final Performance and Stability Validation

**Files:**
- Modify: `src/light_map/rendering/layers/hand_mask_layer.py`
- Modify: `src/light_map/rendering/layers/aruco_mask_layer.py`

**Step 1: Stabilize Foreground Versioning**
Only include `system_time_version` if there are active temporal state (e.g., lingering masks or hulls).

**Step 2: Run benchmark**
Run: `xvfb-run -a python3 scripts/verify_performance.py`
Expected: `RENDER TOTAL` < 50ms during interaction, and ~0ms when stable.
