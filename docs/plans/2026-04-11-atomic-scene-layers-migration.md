# Plan: Fully Migrate Legacy Scenes to the Atomic Layer System

This plan describes the final phase of the rendering refactor: eliminating the `SceneLayer` / `LegacySceneLayer` bridge and replacing it with specialized, data-driven `Layer` implementations for each scene type.

## Objective

1.  **Eliminate the `SceneLayer` bridge:** Remove the pattern where a generic layer delegates rendering to a monolithic `Scene.render()` method.
2.  **Scene-Specific Layers:** Implement dedicated layers (e.g., `CalibrationLayer`, `FlashLayer`) that consume granular `WorldState` atoms and return `ImagePatch`es directly.
3.  **Refactor Scenes to Controllers:** Transition existing `Scene` objects to be pure "Controllers" that handle logic and update `WorldState`, with no rendering responsibility.
4.  **Granular Versioning:** Ensure that only the necessary parts of the screen are re-rendered when a scene's state changes.

## Core Problem

Currently, `SceneLayer` acts as a "black box" bridge. When any part of a scene's state changes, the entire scene is typically re-rendered into a full-screen buffer, which is then converted to BGRA and composited. This is inefficient and bypasses the benefits of the layered system, such as partial-screen updates and independent caching.

## Detailed Changes

### 1. `src/light_map/state/world_state.py`

-   **Refine Calibration Atoms:** Instead of a single `_calibration_atom`, introduce more granular atoms if needed (e.g., `_calibration_target_pos`, `_calibration_progress`).
-   **Flash Atoms:** Add atoms for the `FlashCalibrationScene` (e.g., `active_pulse_index`, `pulse_brightness`).
-   **Map Grid Atoms:** Add atoms for `MapGridCalibrationScene` (e.g., `grid_lines`, `active_handle`).

### 2. New Layer Implementations

Create specialized layers in `src/light_map/rendering/layers/`:

-   **`CalibrationLayer(Layer)`**:
    -   Handles rendering of calibration targets, text instructions, and progress bars.
    -   Reads from `calibration_atom` and `scene_state_atom`.
-   **`FlashLayer(Layer)`**:
    -   Handles rendering of light pulses for structured light detection.
    -   Reads from new flash-specific atoms.
-   **`MapGridLayer(Layer)`**:
    -   Handles rendering of the interactive calibration grid.
    -   Reads from `grid_metadata_atom`.

### 3. Refactor `src/light_map/calibration/calibration_scenes.py`

-   **Remove `render()` methods:** Move all drawing logic (OpenCV calls) into the new `Layer` classes.
-   **Update `update()` methods:** Ensure all state transitions (e.g., changing stages, updating cursor positions) are reflected in `WorldState` atoms.
-   **Scene Payload:** Scenes should continue to return transitions, but they no longer provide pixels.

### 4. `src/light_map/core/layer_stack_manager.py`

-   **Dynamic Layer Injection:** Update the `LayerStackManager` to include the appropriate specialized layers in the stack based on the current active scene.
-   **Remove `SceneLayer`:** Once all scenes are migrated, remove the `SceneLayer` from the default stack.

### 5. `src/light_map/interactive_app.py`

-   **Simplify Main Loop:** Remove the "Update SceneLayer bridge" step.
-   **Unified State Sync:** Ensure the `InteractiveApp` only coordinates state; the layers will react to the state changes automatically.

## Phase-by-Phase Execution

### Phase 1: Infrastructure & Simple Scenes
-   Implement `MapGridLayer`.
-   Migrate `MapGridCalibrationScene` (move its grid rendering to the new layer).
-   Verify that the grid still renders correctly via the new layer.

### Phase 2: Calibration & Flash
-   Implement `CalibrationLayer` and `FlashLayer`.
-   Migrate `IntrinsicsCalibrationScene`, `ProjectorCalibrationScene`, and `FlashCalibrationScene`.
-   These scenes are highly visual but follow predictable patterns.

### Phase 3: The "Big One" (Extrinsics)
-   Refactor `ExtrinsicsCalibrationScene` (the largest file).
-   This will involve breaking down its complex `render()` method into modular rendering logic within `CalibrationLayer`.

### Phase 4: Cleanup
-   Deprecate and remove `SceneLayer` and `LegacySceneLayer`.
-   Clean up any remaining legacy `render()` methods in the `Scene` base class.

## Verification Plan

### Automated Tests
-   Create unit tests for each new Layer type (e.g., `tests/test_calibration_layer.py`).
-   Verify that `get_current_version()` correctly triggers re-renders only when relevant atoms change.
-   Regression test: `pytest tests/test_interactive_app_layered.py`.

### Manual Verification
-   Run the full calibration suite.
-   Observe the `total_render_logic` metrics in the debug overlay; it should remain low or decrease due to more efficient patch-based rendering.
-   Verify that transparency and "blocking" behavior remain correct for all scenes.
