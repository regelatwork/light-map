# Plan: Manual Projector Position Adjustment (Atoms-First)

Allow users to fine-tune the projector's 3D position (X, Y, Z) manually through the frontend. This uses the established `WorldState` atom system to provide real-time visual feedback on the tabletop.

## 1. Backend Changes

### 1.1 Data Model (`src/light_map/common_types.py`)
- Define a `ProjectorPose` dataclass to hold absolute `x`, `y`, and `z` coordinates (float).
- Add `projector_pos_x_override`, `projector_pos_y_override`, and `projector_pos_z_override` (Optional[float]) to `AppConfig` for persistent configuration.

### 1.2 World State (`src/light_map/core/world_state.py`)
- Add `_projector_pose_atom` to `WorldState`, initialized with the current projector position.
- Expose a `projector_pose` property (getter/setter) and a `projector_pose_version` property.
- Update `WorldState.to_dict()` to include the current projector pose.

### 1.3 Projection Logic (`src/light_map/vision/projection.py`)
- Refactor `ProjectionService` to retrieve the projector's position from `state.projector_pose` instead of `projector_model.projector_center`.
- This ensures the math always uses the latest "live" value from the atom.

### 1.4 Layer Versioning
- Update `get_current_version()` in the following layers to include `self.state.projector_pose_version`:
    - `ArucoMaskLayer`
    - `HandMaskLayer`
    - `CursorLayer` (Pointer)
- This ensures that changing the position in the UI immediately invalidates cached frames and triggers a re-render.

### 1.5 Action Handling (`src/light_map/action_dispatcher.py`)
- Update `handle_update_system_config` to process new absolute position values.
- It should update `MapConfigManager` (for persistence) and then update the `WorldState` atom.

### 1.6 State Mirroring (`src/light_map/__main__.py`)
- Include the projector's **Calibrated Position** (from `.npz`) and **Current Position** (from Atom) in the `state_mirror["config"]`.
- This allows the frontend to show the current absolute values and know what the "Reset" target is.

## 2. Frontend Changes

### 2.1 Settings Page
- Add a "Hardware Alignment" tab to the Settings page.
- Implement labeled text boxes for **Projector X, Y, and Z position (mm)**.
- These boxes display the **Absolute Position** from the state.
- **Logic:**
    - On change (debounced): Send the new absolute value to the backend via `POST /config/system`.
    - "Reset to Calibrated" button: Sends `null` for all three coordinates, triggering the backend to revert to the `.npz` values.

### 2.2 API Client
- Update TypeScript types and the API client to support the new `projector_pos_*_override` fields.

## 3. Verification Plan

### 3.1 Automated Tests
- Add a test case to `tests/test_interactive_app_temporal.py` (or similar) verifying that updating the projector pose atom triggers a version bump and reflects in the serialized state.
- Verify `ProjectionService` math handles the pose update correctly.

### 3.2 Manual Verification
- Place a physical marker on the table.
- Open the Settings -> Hardware Alignment tab.
- Manually edit the X coordinate (e.g., add 5mm).
- Verify the projected mask moves horizontally in sync with the typing.
- Click "Reset to Calibrated" and verify it snaps back.
- Restart the app and verify the manual position is still active.
