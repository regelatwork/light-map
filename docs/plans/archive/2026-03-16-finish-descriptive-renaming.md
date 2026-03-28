# Plan: Finish Variable Renaming and Fix Regressions

## Context

A major refactoring effort was initiated to improve code readability and maintainability by replacing cryptic variable names (mostly inherited from OpenCV conventions) with descriptive ones. Additionally, redundant projection math was consolidated into `src/light_map/vision/projection.py`.

During the final stages of the bulk renaming, several regressions were introduced, specifically regarding:

1. **Serialization Compatibility**: `np.savez` and `np.load` calls were updated to use new keys (e.g., `distortion_coefficients`), which broke loading of existing `.npz` files and some unit tests that used the old keys.
1. **InteractiveApp State**: `src/light_map/interactive_app.py` was accidentally overwritten with an incorrect version, leading to import errors and incorrect usage of `SessionManager` (which has static methods only).
1. **Incomplete Renaming**: Some files (like `calibration_scenes.py`) and several test files are in a partially refactored state.

## Target Renaming Mapping

| Old Name | New Name |
| :--- | :--- |
| `rvec` / `camera_rvec` | `rotation_vector` / `camera_rotation_vector` |
| `tvec` / `camera_tvec` | `translation_vector` / `camera_translation_vector` |
| `dist` / `dist_coeffs` | `distortion_coefficients` |
| `mtx` | `camera_matrix` (camera) or `intrinsic_matrix` (projector) |
| `R` | `rotation_matrix` |
| `RT` | `rotation_matrix_inv` |
| `cam_pts` / `proj_pts` | `camera_points` / `projector_points` |
| `obj_points` / `img_points` | `object_points` / `image_points` |

## Immediate Tasks

### 1. Fix `np.load` Backward Compatibility

Ensure all code that loads `.npz` files handles both old and new keys to prevent `KeyError`.

- **File**: `src/light_map/vision/aruco_detector.py` (Partially done, verify `rotation_vector` vs `rvec`).
- **File**: `src/light_map/__main__.py` (Verify loading logic for `camera_calibration.npz` and `camera_extrinsics.npz`).
- **File**: `src/light_map/interactive_app.py` (Check `_load_camera_calibration`).

### 2. Restore `InteractiveApp` and `SessionManager` Usage

- **Issue**: `TypeError: SessionManager() takes no arguments`.
- **Action**: Locate where `SessionManager` is being instantiated and change it to static calls (e.g., `SessionManager.load_for_map(...)`).
- **Issue**: `AttributeError` for `SVGLoader` or `MenuScene` in tests.
- **Action**: Fix imports in `src/light_map/interactive_app.py`. Ensure `SVGLoader` is imported correctly.

### 3. Complete Renaming in `calibration_scenes.py`

- **File**: `src/light_map/scenes/calibration_scenes.py`.
- **Task**: Finish replacing `dist_coeffs`, `rvec`, `tvec`, `camera_rvec`, etc., with their descriptive counterparts. Pay special attention to the `Projector3DCalibrationScene` and its use of `cv2.projectPoints`.

### 4. Fix Broken Unit Tests

The following tests are currently failing and need update to use the new variable names or fixed mocks:

- `tests/test_aruco_detector.py`
- `tests/test_aruco_fov_masking.py`
- `tests/test_aruco_grid_snapping.py`
- `tests/test_extrinsics_calibration_scene.py`
- `tests/test_extrinsics_tdd.py`
- `tests/test_scanning_scene.py`
- `tests/test_token_vertical_projection.py`

### 5. Final Verification

- Run `ruff format .` and `ruff check . --fix`.
- Run `pytest` and ensure all 392 tests pass.

## Success Criteria

- Descriptive names used consistently across all `src/` and `tests/` files.
- Existing calibration files can still be loaded.
- Zero test failures.
