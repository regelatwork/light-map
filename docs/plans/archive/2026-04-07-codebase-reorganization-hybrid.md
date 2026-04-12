# Codebase Reorganization Plan: Hybrid Functional-Technical Structure

## Overview

This plan outlines the transition of the `src/light_map` directory from a flat, crowded structure to a **Hybrid Functional-Technical** organization. The goal is to improve discoverability, reduce root-level clutter, and co-locate related logic, state, and scenes.

## Objectives

- **Reduce Root Clutter:** Move ~40 files from the root to functional domains.
- **Functional Co-location:** Group systems (Map, Menu, Visibility, Calibration) with their respective logic, configuration, and scenes.
- **Architectural Clarity:** Define a clear "dependency floor" in `core/` for shared types and infrastructure.
- **Internal Organization:** Use sub-directories within complex domains (e.g., `vision/detectors`, `rendering/layers`) to maintain a clean hierarchy.

## Target Structure

### 1. Root (`src/light_map/`)

*Only high-level orchestrators and entry points.*

- `__init__.py`: Package metadata.
- `__main__.py`: CLI entry point.
- `interactive_app.py`: Main application controller.
- `action_dispatcher.py`: Central event hub.

### 2. State Management (`src/light_map/state/`)

*The "Source of Truth" for the application.*

- `world_state.py`: Central data repository.
- `versioned_atom.py`: Granular state versioning.

### 3. Core Foundation (`src/light_map/core/`)

*Universal types and engine infrastructure.*

- **Data & Types:** `common_types.py`, `constants.py`, `token_naming.py`.
- **Engine:** `main_loop.py`, `app_context.py`, `layer_stack_manager.py`, `config_store.py`.
- **Base/Utils:** `scene.py` (ABC), `display_utils.py`, `storage.py`, `notification.py`, `analytics.py`.

### 4. Vision System (`src/light_map/vision/`)

*CV detection and frame processing.*

- **`infrastructure/`**: `camera.py`, `camera_operator.py`, `frame_producer.py`, `process_manager.py`, `workers.py`, `tracking_coordinator.py`, `debug_utils.py`.
- **`detectors/`**: `aruco_detector.py`, `flash_detector.py`, `structured_light_detector.py`.
- **`processing/`**: `input_processor.py`, `hand_masker.py`, `token_filter.py`, `token_tracker.py`, `token_merge_manager.py`.
- **`remote/`**: `remote_driver.py`.
- **Scenes:** `scanning_scene.py`.

### 5. Rendering & UI (`src/light_map/rendering/`)

*Projector output and layer composition.*

- **Core:** `renderer.py`, `projector.py`, `projection.py`, `overlay_renderer.py`.
- **Base:** `visibility_base_layer.py`, `scene_layer.py`.
- **`layers/`**:
  - `map_layer.py`, `menu_layer.py`, `fow_layer.py`, `door_layer.py`, `visibility_layer.py`
  - `cursor_layer.py`, `aruco_mask_layer.py`, `hand_mask_layer.py`, `overlay_layer.py`
  - `projector_3d_layer.py`, `selection_progress_layer.py`, `legacy_scene_layer.py`
- **`svg/`**: `loader.py`, `renderer.py`, `blockers.py`, `geometry.py`, `utils.py`.

### 6. Interaction & Input (`src/light_map/input/`)

*User input handling and gesture logic.*

- `input_manager.py`, `input_coordinator.py`, `gestures.py`, `dwell_tracker.py`, `map_interaction.py`.

### 7. Feature Domains (The "Hybrid" Folders)

*Co-locating System + Config + Scene.*

- **`map/`**: `map_system.py`, `map_config.py`, `map_scene.py`, `session_manager.py`.
- **`menu/`**: `menu_system.py`, `menu_builder.py`, `menu_config.py`, `menu_scene.py`.
- **`visibility/`**: `visibility_engine.py`, `fow_manager.py`, `exclusive_vision_scene.py`, `visibility_types.py`.
- **`calibration/`**: `calibration.py`, `calibration_logic.py`, `calibration_scenes.py`.

## Implementation Strategy

### Phase 1: Preparation

- [ ] Create all new directories and sub-directories.
- [ ] Add `__init__.py` files to all new directories.

### Phase 2: The "Big Move"

- [ ] Move files according to the target structure.
- [ ] Update imports in all moved files. Use **absolute imports** (e.g., `from light_map.state.world_state import WorldState`).
- [ ] **Circular Dependency Mitigation:** Use string type hints (`"WorldState"`) and `from __future__ import annotations` in files that import `WorldState` solely for type-checking.

### Phase 3: Test & CLI Update

- [ ] Update `pytest` configurations and file references in `tests/`.
- [ ] Update `scripts/` to reflect new import paths.
- [ ] Run full test suite.

## Constraints & Risks

- **Circular Dependencies:** Moving `WorldState` to `state/` helps isolate it. Avoid importing high-level domains (like `menu`) into `state/` if possible; consider moving specific State dataclasses (like `MenuState`) into a shared types file if needed.
- **Import Noise:** High-churn change.
- **Test Integrity:** Every test file in `tests/` will need its imports updated.
