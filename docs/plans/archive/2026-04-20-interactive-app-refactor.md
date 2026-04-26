# Interactive App Refactor Implementation Plan

> **For Gemini:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Decompose `InteractiveApp` into specialized managers and enforce the Read/Write invariant.

**Architecture:** Use tiered `AppContext` objects to provide process-specific services. `InteractiveApp` becomes a bootstrapper. `PersistenceService`, `SceneManager`, and `EnvironmentManager` handle mutations.

**Tech Stack:** Python 3.10+, multiprocessing, versioned Atoms (WorldState).

---

### Phase 1: Tiered Contexts & Persistence Service
This phase establishes the new `AppContext` structure and moves all File I/O and configuration logic out of `InteractiveApp` and `ActionDispatcher`.

**Task 1: Define Tiered Contexts**
- Modify: `src/light_map/core/app_context.py` to add `MainContext`, `VisionContext`, and `RemoteContext`.
- **Constraint:** `VisionContext` and `RemoteContext` **must** be picklable (no `Renderer`, `MapSystem`, or `numpy` buffers).
- Test: Create `tests/test_context_tiers.py` with a `pickle.dumps()` test for each context.

**Task 2: Implement `PersistenceService`**
- Create: `src/light_map/persistence/persistence_service.py`
- **Interface:** Define `load_map(filename)`, `save_session()`, `update_token(id, **kwargs)`, and `update_grid(map_path, **kwargs)`.
- Move: Logic from `InteractiveApp` and `ActionDispatcher` handlers into these methods.
- Test: `tests/test_persistence_service.py` verifying both disk sync (JSON/NPZ) and `WorldState` version increments.

---

### Phase 2: Environment & Scene Managers
Move the "brain" logic—visibility calculations and the state machine—to dedicated managers.

**Task 3: Implement `EnvironmentManager`**
- Create: `src/light_map/vision/environment_manager.py`
- Move: `_sync_vision`, `_rebuild_visibility_stack`, and `_sync_blockers_to_state` from `InteractiveApp`.
- Test: `tests/test_environment_manager.py` with mock token movements triggering FoW updates.

**Task 4: Implement `SceneManager`**
- Create: `src/light_map/core/scene_manager.py`
- Move: Scene initialization, `_switch_scene` logic, and layer stack ordering from `InteractiveApp`.
- Implement: A declarative transition table `(SceneId, Action) -> SceneId`.
- Test: `tests/test_scene_manager.py` verifying state transitions and layer stack correctness.

---

### Phase 3: The Bootstrapper (`InteractiveApp`)
Refactor the original class to use the new managers and contexts.

**Task 5: Refactor `InteractiveApp` Initialization**
- Modify: `src/light_map/interactive_app.py`
- Job: Instantiate Managers, populate Contexts, and delegate all `process_state` logic to the managers.
- Test: `tests/test_interactive_app_bootstrapper.py` ensuring all services are initialized correctly.

---

### Phase 4: Final Integration & Cleanup
Clean up the legacy handlers and perform end-to-end validation.

**Task 6: Clean `ActionDispatcher`**
- Modify: `src/light_map/action_dispatcher.py`
- Job: Replace complex handlers with simple calls to `PersistenceService`, `SceneManager`, or `EnvironmentManager`.
- Test: `tests/test_action_dispatcher_clean.py`.

**Task 7: Global Verification**
- Run all existing tests (`pytest tests/`) to ensure no regressions in E2E behavior.
- Validate manual walkthrough of App startup and map loading.
