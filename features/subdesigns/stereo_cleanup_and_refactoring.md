# Sub-Design Specification: Post-Implementation Cleanup & Refactoring Plan

## 1. Overview & Objectives

This sub-design specifies the post-implementation cleanup, refactoring, and deprecation tasks required after the dual-camera stereographic vision system is fully implemented in `light_map`.

It ensures that legacy single-camera abstractions, dead code, stale test mocks, and configuration collisions are systematically refactored and cleaned up without leaving technical debt.

______________________________________________________________________

## 2. Core Codebase Refactoring (`src/light_map/`)

### 2.1 `AppContext` & System Lifecycle

- **`AppContext.camera` Transition:** Deprecate single-camera handle `AppContext.camera` in favor of `AppContext.camera_manager` (`MultiCameraManager`), providing clean API access to `left` and `right` streams.
- **Process Lifecycle:** Update `VisionProcessManager` to supervise dual camera processes (`CameraOperator(id="left")` and `CameraOperator(id="right")`).

### 2.2 IPC & Shared Memory Classes

- **Constructor Signatures:** Update `CameraOperator` and `FrameProducer` constructors to accept `camera_id` ("left" / "right"), `shm_name`, and a shared `mp.Lock()` instance.
- **Buffer Layout Migration:** Replace legacy single-buffer layout code with slot-based 64-byte `FrameHeader` struct (`<qqiiiii`) unpacking.

### 2.3 `Token` Dataclass Alignment

- **3D Property Standardization:** Standardize `Token` on 3D spatial properties (`world_x`, `world_y`, `world_z` in mm) and `is_stereo_triangulated`, deprecating legacy monocular 2D marker fields.

______________________________________________________________________

## 3. Scripts & Data File Cleanup (`scripts/`)

### 3.1 Calibration Script Updates

- **`scripts/generate_calibration_target.py`:** Update SVG generator script to produce target SVG using `cv2.aruco.DICT_4X4_50` and IDs **`40` & `41`**.
- **`scripts/projector_calibration.py`:** Wrap or refactor standalone script to trigger the single-sweep stereo calibration wizard.

### 3.2 Data File Deprecation

- **Intrinsics Fallback:** Retain `camera_calibration.npz` as fallback for shared lens intrinsics.
- **Extrinsics Deprecation:** Deprecate reliance on `camera_extrinsics.npz` in favor of structured `stereo_calibration.json`.

______________________________________________________________________

## 4. Test Suite Refactoring (`tests/`)

### 4.1 Mock Camera Fixes

- **Test Pipeline Mocks:** Update test files (`tests/test_aruco_detector.py`, `tests/test_environment_manager.py`, `tests/test_extrinsics_calibration_scene.py`) that instantiate single `CameraOperator` or camera matrix mocks to use `MockMultiCameraManager` / `MockFrameProducer`.

### 4.2 Tactical Case Updates

- **Tactical Test Suite:** Update golden cases in `tests/tactical_cases/` to supply 3D tabletop vectors $(X, Y, Z\_{mm})$ to the visibility engine and cover calculator.

### 4.3 Schema Sync Verification

- **`tests/test_config_sync.py`:** Verify that `generate_ts_schema.py` outputs matching `CameraDeviceSchema` and `StereoVisionConfigSchema` interfaces in `schema.generated.ts`.

______________________________________________________________________

## 5. Configuration & Documentation Updates (`docs/` & `tokens.json`)

### 5.1 `tokens.json` Scrub

- **ID Partitioning Enforcement:** Remove legacy test token definitions (such as ID `"42"`) from `tokens.json` to ensure user tokens strictly occupy IDs `0–39`, leaving `40–49` reserved for calibration system targets.

### 5.2 System Documentation Updates

- **Documentation Sync:** Update `docs/calibration.md`, `docs/configuration.md`, and `docs/architecture.md` to document the 128mm baseline setup, IDs `40–41` & `42–49`, and `stereo_calibration.json`.

______________________________________________________________________

## 6. Verification Criteria

- [ ] All single-camera references in `AppContext` and `VisionProcessManager` migrated to `MultiCameraManager`.
- [ ] `generate_calibration_target.py` outputs SVG with IDs 40 & 41 using `DICT_4X4_50`.
- [ ] `tokens.json` contains zero user token definitions in the reserved range `40–49`.
- [ ] Entire `pytest` test suite passes cleanly with updated dual-camera mocks.
- [ ] System documentation in `docs/` reflects the completed dual-camera stereographic architecture.
