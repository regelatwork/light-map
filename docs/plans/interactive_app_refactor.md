# Design: InteractiveApp Refactor & Timestamp-based Change Tracking

## Overview
Currently, `InteractiveApp.py` is overly complex and relies on manual boolean "dirty flags" (`is_dirty`) to coordinate rendering between scenes, layers, and the main loop. This pattern is error-prone, violates separation of concerns, and causes "stale" or "lost" update issues when multiple consumers are involved.

This design proposes a robust **Timestamp-based Synchronization** mechanism and the extraction of several core responsibilities into specialized managers.

## 1. Timestamp-based Change Tracking

### Core Principle
Instead of a boolean `is_dirty`, producers increment a version counter (timestamp). Consumers store the `last_seen_version`. If `producer.version > consumer.last_seen_version`, the consumer is dirty. This is implemented atomically: the `render()` method should return the version it just satisfied to ensure the renderer knows exactly what is in its cache.

### Changes
#### `Layer` Base Class
- Replace `is_dirty` (boolean property) with `get_current_version() -> int`.
- Each layer subclass calculates its current logical version from its `WorldState` dependencies (e.g., `viewport_timestamp`, `map_timestamp`).
- Update `render(current_time) -> Tuple[List[ImagePatch], int]` to return both the patches and the version that was rendered.

#### `Renderer`
- Store `last_layer_versions: Dict[Layer, int]` to track what is currently in its buffers/cache.
- In `render()`, compare `layer.get_current_version()` with `last_layer_versions`.
- If `current > last`, call `layer.render()`, update `last_layer_versions`, and recomposite.
- This eliminates the "dirty flag" as a stored boolean entirely, moving to a pure "version comparison" model.

#### `Scene` Base Class
- Remove `_is_dirty` boolean.
- Add `version: int` (monotonically increasing).
- Add `is_dynamic: bool` (default `False`).
- Add `mark_dirty()` method to increment `version`.

#### `WorldState`
- Add `fow_timestamp: int`.
- Add `increment_fow_timestamp()` method.

#### `FogOfWarLayer`
- Remove `self._is_dirty`.
- `is_dirty` property checks `state.fow_timestamp`, `state.viewport_timestamp`, and `state.visibility_timestamp`.

#### `InteractiveApp`
- Remove manual `is_dirty = True/False` assignments for scenes and layers.
- In the `update()` loop:
  ```python
  if self.current_scene.is_dynamic or self.current_scene.version > self.last_scene_version:
      state.increment_scene_timestamp()
      self.last_scene_version = self.current_scene.version
  ```

## 2. Structural Refactoring

To reduce the complexity and size of `InteractiveApp.py` (~1300 lines), the following components will be extracted:

### `LayerStackManager`
- Responsible for determining which layers are active.
- Handles the transition between the "Standard" and "Exclusive Vision" (Token Inspection) stacks.
- Configures layer parameters (opacity, quality) based on current scene state.

### `ActionDispatcher`
- Replaces the large `_handle_payloads` method.
- Uses a registry-based approach for action handlers.
- Each handler takes `AppContext` and `WorldState`.

### `InputCoordinator`
- Moves the logic for normalizing vision inputs (MediaPipe landmarks vs. standardized HandInput from Remote Driver) out of the main loop.
- Handles input expiration/caching logic.

## 3. Implementation Sub-tasks

1. **[Refactor] Scene Versioning Mechanism**: Implement version-based sync for Scenes (Completed).
2. **[Refactor] FogOfWar Timestamp Synchronization**: Implement `fow_timestamp` and update `FogOfWarLayer` (Completed).
3. **[Refactor] Layer & Renderer Atomic Versioning**: Move Layer and Renderer to a pure version-comparison interface and return version from `render()`.
4. **[Refactor] Extract LayerStackManager**: Decouple layer selection logic.
5. **[Refactor] Extract ActionDispatcher**: Decouple action handling logic.
6. **[Refactor] Extract InputCoordinator**: Decouple input normalization.
7. **[Cleanup] Eliminate stale flags**: Remove unused `is_dirty` from `WorldState` and other locations.
