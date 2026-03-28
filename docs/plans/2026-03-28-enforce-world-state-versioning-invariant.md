# Plan: Enforce Versioning Invariant in WorldState (Data-Driven Versioning)

This plan describes the refactoring of `WorldState` to ensure that versioning is an internal invariant driven purely by meaningful data changes, eliminating the need for manual version manipulation or "invalidation" methods.

## Objective
The primary goal is to remove public setters for all `*_version` properties in `WorldState` and replace them with actual data state objects. Versioning should only change as a side-effect of state updates, ensuring that `WorldState` remains the single source of truth and preventing "version spaghetti". If a component needs to trigger a re-render, it must do so by updating the corresponding data in `WorldState`.

## Core Problem
Currently, several production components (e.g., `interactive_app.py`, `input_coordinator.py`) use `state.xxx_version += 1` to manually trigger re-renders. This is problematic because:
1. It bypasses the `VersionedAtom` equality checks.
2. It uses dummy atoms (e.g., `_fow_atom` initialized to `0`) just to act as event triggers.
3. It violates the invariant that versioning should only change when there is a meaningful data change.
4. "Invalidation" methods are just a different name for a version change without a data change, which still violates the invariant.

## Detailed Changes

### 1. `src/light_map/core/world_state.py`

#### Class Documentation
Update the `WorldState` class docstring to explicitly state the versioning invariant:
```python
"""
Central Data Repository (The "Source of Truth") for the MainProcess.
Manages background frames, vision results, and granular versioning for caching.

Versioning Invariant:
All version properties (e.g., scene_version, tokens_version) are READ-ONLY from external
classes. Versioning is an internal invariant managed by VersionedAtom. External entities
must NEVER manipulate these versions directly or use invalidation methods. A version update
must ONLY occur as a natural side-effect of a meaningful data change in the underlying atom.
"""
```

#### Migrate Dummy Atoms to Data Atoms
Remove atoms that hold dummy integers and replace them with actual state data:
- **`_map_atom`**: Remove this. Introduce `_map_render_state_atom` holding a `MapRenderState` dataclass (opacity, quality, filepath).
- **`_fow_atom`**: Remove this. `fow_manager` should push its updated state/mask to `WorldState` via a `fow_mask` property, allowing `VersionedAtom` to detect changes.
- **`_visibility_aggregate_version_atom`**: Remove this. Depend purely on `_visibility_mask_atom` which holds the actual numpy array mask.
- **`_scene_atom`**: Only updates when `current_scene_name` changes. Time-based scene animations should rely on `system_time_version` or a new `scene_time_version`.

#### Remove Setters and Invalidation Methods
Remove the `@property.setter` methods for all `*_version` properties. Do not introduce `invalidate_xxx()` methods.

### 2. Update Production Code

Systematically replace all instances of manual version bumping (`version += 1`) with true data mutations:

- **`src/light_map/interactive_app.py`**:
  - Replace `self.state.map_version += 1` by updating a new `self.state.map_render_state = MapRenderState(...)`.
  - Replace `self.state.fow_version += 1` by updating `self.state.fow_mask = self.fow_manager.mask.copy()`.
  - Replace `self.state.visibility_version += 1` by ensuring `self.state.visibility_mask = ...` is called correctly.
  - Replace `self.state.tokens_version += 1` (on `TOKEN_ADD`) by assigning a new list: `self.state.tokens = list(self.state.tokens) + [new_token]`.
- **`src/light_map/core/scene.py`**:
  - Replace `self.context.state.scene_version += 1` with dependencies on time/animations (e.g., checking `system_time_version`) or by exposing specific scene state to `WorldState`.
- **`src/light_map/action_dispatcher.py`**:
  - Replace `app.state.fow_version += 1` with an update to the actual FOW state in `WorldState`.
- **`src/light_map/input_coordinator.py`**:
  - Remove `state.hands_version += 1`. Ensure time-based logic (like dwell) relies on `system_time_version` rather than pretending hand data changed when it didn't.
- **`src/light_map/core/layer_stack_manager.py`**:
  - Remove `self.context.state.map_version += 1` and update the `map_render_state` data object in `WorldState` instead.

### 3. Update Tests

Update all tests that were manually manipulating versions to simulate actual data changes:

- **`tests/test_overlay_layer.py`**: Update actual `tokens` data.
- **`tests/test_fow_layer.py`**: Update the `fow_mask` data instead of bumping `fow_version`.
- **`tests/test_map_layer.py`**: Update `map_render_state`.
- **`tests/test_scene_layer.py`**: Use `system_time` for animation tests instead of `scene_version`.
- **`tests/test_door_layer.py`**: Update `visibility_mask` data directly.

## Junior Developer Guide: Why This Matters

In a complex system like Light Map, multiple components depend on knowing when state has changed to re-render. 

1. **The Old Way**: An external class could say `state.tokens_version += 1`. This "forced" a re-render even if the tokens hadn't actually changed. It bypassed our equality checks and created a "version spaghetti" where we lost track of *why* things were rendering.
2. **The New Way**: Versioning is completely automatic and based on *data*. If you want the map version to change, you must change the map data (e.g., `state.map_render_state = new_state`). The `VersionedAtom` inside `WorldState` will automatically detect the change and bump the version.
3. **Animations and Time**: If you need something to re-render constantly (like a pulsing animation), you don't pretend the data changed. Instead, your renderer should look at `state.system_time_version`. Time is always changing, so this is the correct way to drive animations without corrupting our static data versions.

## Verification Plan

### Automated Tests
Run the following commands to ensure no regressions:
- `pytest tests/test_world_state_timestamps.py` (Verifies versioning logic)
- `pytest tests/test_overlay_layer.py` (Verifies rendering still works)
- `pytest tests/test_interactive_app_render_regression.py` (Verifies end-to-end rendering)

### Static Analysis
Run `grep -r "_version += 1" src/` and `grep -r ".xxx_version =" src/` to ensure no manual version assignments remain in the production code.
