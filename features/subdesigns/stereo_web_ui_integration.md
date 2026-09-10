# Sub-Design Specification: Web UI & Backend Integration

## 1. Overview & Objectives

This sub-design specifies the backend Pydantic configuration schemas, Action Dispatcher handlers, static TypeScript code generation, and React frontend UI components for configuring, calibrating, and monitoring the dual-camera stereographic vision system in `light_map`.

It adheres strictly to `light_map`'s **Typed Config Synchronization** architecture (SSOT in Python Pydantic models, auto-generated TypeScript interfaces, and metadata-driven React UI components).

______________________________________________________________________

## 2. Backend Pydantic Schemas (`src/light_map/core/config_schema.py`)

### 2.1 Camera Device Schema

```python
class CameraDeviceSchema(BaseModel):
    device_path: str = Field(
        default="/dev/video0", title="Device Path", description="V4L2 device file path"
    )
    role: str = Field(default="left", title="Role", description="Camera role (left or right)")
    intrinsics_file: str = Field(
        default="camera_calibration.npz",
        title="Intrinsics File",
        description="Camera lens distortion parameters file",
    )
    crop_roi: list[int] | None = Field(
        default=None, title="Sensor Crop ROI", description="Hardware selection crop [x, y, w, h]"
    )
```

### 2.2 Stereo Vision Configuration Schema

```python
class StereoVisionConfigSchema(BaseModel):
    enabled: bool = Field(
        default=True,
        title="Enable Stereo Vision",
        description="Master toggle for dual-camera stereographic tracking",
    )
    baseline_separation_mm: float = Field(
        default=128.0,
        title="Baseline Separation (mm)",
        description="Distance between camera optical centers in mm",
    )
    cameras: list[CameraDeviceSchema] = Field(
        default_factory=list, title="Camera Devices", description="Configured camera sensors"
    )
    max_parallax_margin_mm: float = Field(
        default=200.0,
        title="Max Parallax Margin (mm)",
        description="Vertical 3D volume envelope for sensor ROI calculation",
    )
    reprojection_error_threshold: float = Field(
        default=3.0,
        title="Reprojection Threshold (px)",
        description="Maximum allowed reprojection error for 3D triangulation",
    )
```

### 2.3 SSOT Global Embedding (`GlobalConfigSchema`)

To integrate with state synchronization and storage persistence, `GlobalConfigSchema` embeds the stereo schema:

```python
class GlobalConfigSchema(BaseModel):
    # Existing global fields ...
    stereo_vision: StereoVisionConfigSchema = Field(
        default_factory=StereoVisionConfigSchema,
        title="Stereo Vision Settings",
        description="Configuration for dual-camera stereographic tracking",
    )
```

______________________________________________________________________

## 3. Calibration Triggering & Dispatcher Integration

The system supports two complementary entry points for launching the unified stereo calibration:

1. **On-Tabletop Projector Menu:** Triggered directly on the gaming surface via hand gesture or pointer interaction through the hierarchical menu.
1. **Web Dashboard Panel:** Triggered remotely from the browser on the Calibration Wizards panel (`/input/action`).

### 3.1 Common Types & Actions (`src/light_map/core/common_types.py`)

- **`MenuActions.CALIBRATE_STEREO = "CALIBRATE_STEREO"`**: Enumerated action identifier shared across the tabletop menu and API.
- **`SceneId.CALIBRATE_STEREO = "CALIBRATE_STEREO"`**: Active scene identifier for the stereo calibration routine.

### 3.2 Tabletop Menu System (`src/light_map/menu/`)

- **`menu_builder.py`**:
  Adds a new menu item under the `"Calibration"` submenu:

  ```python
  MenuItem(
      title="6. Stereo Vision Calibration",
      action_id=MenuActions.CALIBRATE_STEREO,
      should_close_on_trigger=True,
  )
  ```

  *(Optionally dynamically visible or highlighted when `global_config.stereo_vision.enable_stereo` is active).*

- **`menu_scene.py`**:
  Handles the menu action trigger:

  ```python
  elif action == MenuActions.CALIBRATE_STEREO:
      return SceneTransition(SceneId.CALIBRATE_STEREO)
  ```

### 3.3 Action Dispatcher Integration (`src/light_map/action_dispatcher.py`)

Following `light_map`'s WebSocket / Action Dispatcher architecture, stereo calibration triggers are handled through `/input/action`:

```python
# Registered Action Payload Handlers in action_dispatcher.py:
ActionType.START_STEREO_CALIBRATION = "START_STEREO_CALIBRATION"
ActionType.SAVE_STEREO_CALIBRATION = "SAVE_STEREO_CALIBRATION"
ActionType.UPDATE_STEREO_CONFIG = "UPDATE_STEREO_CONFIG"
```

In `_handle_menu_transition()`:

```python
scene_map = {
    # Existing calibrations...
    MenuActions.CALIBRATE_STEREO: SceneId.CALIBRATE_STEREO,
    ActionType.START_STEREO_CALIBRATION: SceneId.CALIBRATE_STEREO,
}
```

### 3.4 Handler Behavior & Scene Lifecycle

- **Launch (`CALIBRATE_STEREO` / `START_STEREO_CALIBRATION`)**: Transitions `SceneManager` to `SceneId.CALIBRATE_STEREO`, activating `StereoCalibrationScene`. Signals dual `CameraOperator` processes to revert from hardware ROI cropping to uncropped full-frame capture mode.
- **Solve & Save (`SAVE_STEREO_CALIBRATION`)**: Invokes `StereoCalibrationWizard.run_calibration()`, writes solved extrinsics and hardware sensor ROIs to `stereo_calibration.json`, updates `stereo_vision` in `GlobalConfig`, and commands `CameraOperator` processes to transition into high-speed cropped ROI mode.
- **Config Update (`UPDATE_STEREO_CONFIG`)**: Validates incoming Pydantic schema update payload and syncs values to `AppConfig` runtime state.

______________________________________________________________________

## 4. TypeScript Schema Auto-Generation (`scripts/generate_ts_schema.py`)

The generator script `scripts/generate_ts_schema.py` is updated to include `CameraDeviceSchema` and `StereoVisionConfigSchema` in its `schemas` list, generating types in `frontend/src/types/schema.generated.ts`:

```typescript
// Auto-generated by scripts/generate_ts_schema.py
export interface CameraDeviceSchema {
  device_path: string;
  role: 'left' | 'right';
  intrinsics_file: string;
  crop_roi?: [number, number, number, number] | null;
}

export interface StereoVisionConfigSchema {
  enabled: boolean;
  baseline_separation_mm: number;
  cameras: CameraDeviceSchema[];
  max_parallax_margin_mm: number;
  reprojection_error_threshold: number;
}

export interface StereoDiagnostics {
  left_camera_fps: number;
  right_camera_fps: number;
  stereo_match_ratio: number;
  active_mode: 'FULL_FRAME' | 'HIGH_SPEED_ROI';
}
```

______________________________________________________________________

## 5. Frontend React Component Architecture (`frontend/src/components/`)

### 5.1 Stereo Vision Dashboard (`frontend/src/components/StereoVisionDashboard.tsx`)

A dedicated dashboard tab/modal component for live multi-camera monitoring:

- **Dual Live Video Feeds:** Side-by-side video feeds for Camera Left and Camera Right.
- **Stereo Diagnostics Card:**
  - Gauges for Left FPS and Right FPS.
  - Stereo Pair Match Ratio progress bar (`stereo_match_ratio`).
  - Active Mode badge (`HIGH_SPEED_ROI` vs `FULL_FRAME`).

### 5.2 Single-Sweep Calibration Wizard (`CalibrationWizard.tsx`)

Integrates stereo calibration directly into the web dashboard's Calibration Wizards panel:

- **System Enums (`frontend/src/types/system.ts`):**
  - Adds `CALIBRATE_STEREO = 'CALIBRATE_STEREO'` to `SceneId`.
  - Adds `CALIBRATE_STEREO = 'CALIBRATE_STEREO'` to `MenuActions`.
- **Launch Button (`CalibrationWizard.tsx`):**
  Adds a button under the "Launch Calibration" sidebar alongside single-camera routines:
  ```tsx
  <button
    className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-left transition-colors"
    onClick={() => handleStartCalibration(MenuActions.CALIBRATE_STEREO)}
    disabled={isCalibrating}
  >
    5. Stereo Vision Calibration
  </button>
  ```
- **User Instructions Card:**
  Displays actionable step-by-step instructions when `world.scene === SceneId.CALIBRATE_STEREO`:
  ```tsx
  {world.scene === SceneId.CALIBRATE_STEREO && (
    <div className="space-y-2 text-gray-600">
      <p className="font-medium text-gray-800">Single-Sweep Stereo Calibration Active:</p>
      <ul className="list-disc pl-5 space-y-1">
        <li>Place 4 elevated PC tokens (IDs 0–3: Cricket, Lace, Shikra, Verita) on the illuminated corner target rings.</li>
        <li>Place the physical PPI sheet (IDs 40 & 41) flat on the table within both camera views.</li>
        <li>Ensure projected grid markers (IDs 42–49) are unobstructed on the table surface.</li>
      </ul>
      <p className="text-sm text-gray-500">
        The system will solve relative camera translation (+Tx), rotation, table homography, and digital sensor crops in a single pass.
      </p>
    </div>
  )}
  ```
- **Live Stream Preview:** Automatically switches the live feed view or provides side-by-side feeds for dual camera streams.
- **AR Verification Preview:** Renders real-time 3D wireframe box preview over detected physical tokens upon completion.

### 5.3 Settings & Configuration Controls (`SettingsModal.tsx` & `ConfigurationSidebar.tsx`)

- Renders metadata-driven form controls for `stereo_vision` fields (`baseline_separation_mm`, camera device path dropdowns, enable toggle) bound directly to `useSystemState()`.

______________________________________________________________________

## 6. Verification Criteria

- [ ] `CameraDeviceSchema` and `StereoVisionConfigSchema` added to `config_schema.py` and embedded in `GlobalConfigSchema`.
- [ ] `scripts/generate_ts_schema.py` imports new schemas and executes cleanly, updating `schema.generated.ts`.
- [ ] `MenuActions.CALIBRATE_STEREO` and `SceneId.CALIBRATE_STEREO` defined in backend `common_types.py` and frontend `system.ts`.
- [ ] Tabletop hierarchical menu (`menu_builder.py` and `menu_scene.py`) contains `"6. Stereo Vision Calibration"` and transitions to `SceneId.CALIBRATE_STEREO`.
- [ ] Action Dispatcher handles `CALIBRATE_STEREO` / `START_STEREO_CALIBRATION` and `SAVE_STEREO_CALIBRATION` actions via `/input/action`.
- [ ] `CalibrationWizard.tsx` includes `"5. Stereo Vision Calibration"` button and instructions card, launching the calibration scene remotely.
- [ ] `StereoVisionDashboard.tsx` renders dual camera feeds and live diagnostic metrics.
