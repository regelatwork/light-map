# Design: InteractiveApp Refactor & Timestamp-based Change Tracking

## Overview

Currently, `InteractiveApp.py` is overly complex and relies on manual boolean "dirty flags" (`is_dirty`) to coordinate rendering between scenes, layers, and the main loop. This pattern is error-prone, violates separation of concerns, and causes "stale" or "lost" update issues when multiple consumers are involved.

This design proposes a robust **Timestamp-based Synchronization** mechanism and the extraction of several core responsibilities into specialized managers.

## 1. Timestamp-based Change Tracking

### Core Principle

The system has moved away from manual boolean "dirty flags" (`is_dirty`) to a strictly monotonic version counter (timestamp) using `time.monotonic_ns()`.

- **Producers**: Increment a specialized version in `WorldState` when data changes.
- **Consumers**: Store the `last_seen_version`. If `producer.version > consumer.last_seen_version`, the consumer is stale and triggers an update.

This ensures atomic updates: the `render()` method returns the version it just satisfied to ensure the renderer knows exactly what is in its cache.

### Changes

#### `Layer` Base Class

- Replaced `is_dirty` (boolean property) with `get_current_version() -> int`.
- Each layer subclass calculates its current logical version from its `WorldState` dependencies (e.g., `viewport_timestamp`, `map_timestamp`).
- Updated `render(current_time) -> Tuple[List[ImagePatch], int]` to return both the patches and the version that was rendered.

#### `Renderer`

- Stores `last_layer_versions: Dict[Layer, int]` to track current buffer/cache state.
- In `render()`, compares `layer.get_current_version()` with `last_layer_versions`.
- This eliminates the legacy "dirty flag" entirely.

#### `Scene` Base Class

- Removed `_is_dirty` boolean.
- Uses centralized `version: int` (derived from `WorldState.scene_timestamp`).
- Replaced `mark_dirty()` with `increment_version()`.

#### `WorldState`

- Central repository for all versions, issued via `_get_next_version()`.
- Includes `fow_timestamp`, `map_timestamp`, `tokens_timestamp`, etc.

#### `FogOfWarLayer`

- Removed manual `_is_dirty` flag.
- `get_current_version()` property checks `state.fow_timestamp`, `state.viewport_timestamp`, and `state.visibility_timestamp`.

#### `InteractiveApp`

- Removed manual `is_dirty = True/False` assignments.
- In the `process_state()` loop, `last_scene_version` is used to detect if the scene has updated.


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
1. **[Refactor] FogOfWar Timestamp Synchronization**: Implement `fow_timestamp` and update `FogOfWarLayer` (Completed).
1. **[Refactor] Layer & Renderer Atomic Versioning**: Move Layer and Renderer to a pure version-comparison interface and return version from `render()`.
1. **[Refactor] Extract LayerStackManager**: Decouple layer selection logic.
1. **[Refactor] Extract ActionDispatcher**: Decouple action handling logic.
1. **[Refactor] Extract InputCoordinator**: Decouple input normalization.
1. **[Cleanup] Eliminate stale flags**: Remove unused `is_dirty` from `WorldState` and other locations.
