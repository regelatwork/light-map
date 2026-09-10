# Sub-Design Specification: Web UI & Backend Integration

## 1. Overview & Objectives

This sub-design specifies the backend Pydantic configuration schemas, Action Dispatcher handlers, static TypeScript code generation, and React frontend UI components for configuring, calibrating, and monitoring the dual-camera stereographic vision system in `light_map`.

It adheres strictly to `light_map`'s **Typed Config Synchronization** architecture (SSOT in Python Pydantic models, auto-generated TypeScript interfaces, and metadata-driven React UI components).

______________________________________________________________________

## 2. Backend Pydantic Schemas (`src/light_map/core/config_schema.py`)

### 2.1 Camera Device Schema

```python
class CameraDeviceSchema(BaseModel):
    device_path: str = Field(..., title="Device Path", description="Path to the camera device.")
    name: str = Field(default="Camera", title="Name", description="Display name for the camera.")
    enabled: bool = Field(
        default=True, title="Enabled", description="Whether the camera is enabled."
    )
```

### 2.2 Stereo Vision Configuration Schema

```python
class StereoVisionConfigSchema(BaseModel):
    enable_stereo: bool = Field(
        default=False,
        title="Enable Stereo",
        description="Toggle for dual-camera stereographic tracking.",
    )
    baseline_separation_mm: float = Field(
        default=128.0,
        ge=1.0,
        le=500.0,
        title="Baseline Separation (mm)",
        description="Physical distance between the two camera sensors in millimeters.",
    )
    camera_left_device: str = Field(
        default="/dev/video0",
        title="Left Camera Device",
        description="Device path for the left camera.",
    )
    camera_right_device: str = Field(
        default="/dev/video1",
        title="Right Camera Device",
        description="Device path for the right camera.",
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

### 3.3 Action Dispatcher & Defensive Validation (`src/light_map/action_dispatcher.py`)

Action dispatching routes `MenuActions.CALIBRATE_STEREO` uniformly across both tabletop menu triggers and remote Web UI requests:

```python
# In ActionDispatcher._handle_menu_transition():
if action_name == MenuActions.CALIBRATE_STEREO:
    # Defensive guard: verify stereo vision is configured and enabled
    if not self.app.app_config.stereo_vision.enable_stereo:
        self.app.notifications.add_notification(
            "Stereo vision calibration requires dual cameras enabled in configuration."
        )
        return None
    return SceneTransition(SceneId.CALIBRATE_STEREO)
```

### 3.4 Manager-Only Writes & Persistence (`PersistenceService`)

In compliance with the project's strict architectural invariants (`AGENTS.md`):

- **No Direct Disk or State Setters:** Neither `ActionDispatcher` nor `StereoCalibrationScene` may write directly to disk or mutate `WorldState` fields directly.
- **Persistence Delegation:** Saving calibration results is delegated exclusively to `PersistenceService`:
  ```python
  # Added to PersistenceService:
  def save_stereo_calibration(self, calibration_data: dict) -> None:
      """
      Persists stereo calibration results to stereo_calibration.json,
      updates the GlobalConfig stereo_vision settings atomically,
      and notifies the WorldState.
      """
      storage_path = self.storage.get_data_path("stereo_calibration.json")
      with open(storage_path, "w") as f:
          json.dump(calibration_data, f, indent=2)
      # Atomically update global config state through managers
      self.update_global_config_stereo(...)
  ```

### 3.5 Scene ID State Synchronization (`SceneManager`)

To fix frontend state inspection (`world.scene === SceneId.CALIBRATE_STEREO`), `SceneManager.transition_to()` must record the canonical `SceneId` value into `_scene_atom` rather than the Python class name:

```python
# In SceneManager.transition_to():
self.state._scene_atom.update(self.current_scene_id.value)
```

This ensures `world.scene` in the React frontend contains `"CALIBRATE_STEREO"`, enabling proper button disabled states and instruction card rendering.

______________________________________________________________________

## 4. TypeScript Schema Auto-Generation (`scripts/generate_ts_schema.py`)

The generator script `scripts/generate_ts_schema.py` imports `CameraDeviceSchema` and `StereoVisionConfigSchema` and generates their corresponding interfaces and metadata registries in `frontend/src/types/schema.generated.ts`:

```typescript
// Auto-generated by scripts/generate_ts_schema.py
export interface CameraDevice {
  device_path: string;
  name: string;
  enabled: boolean;
}

export interface StereoVisionConfig {
  enable_stereo: boolean;
  baseline_separation_mm: number;
  camera_left_device: string;
  camera_right_device: string;
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
  Adds buttons aligned 1:1 with the Tabletop Menu:
  ```tsx
  {/* Existing 1-4... */}
  <button
    className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-left transition-colors"
    onClick={() => handleStartCalibration(MenuActions.CALIBRATE_PROJECTOR_3D)}
    disabled={isCalibrating}
  >
    5. Projector 3D Pose
  </button>

  <button
    className={`px-4 py-2 text-white rounded text-left transition-colors ${
      !systemConfig.stereo_vision?.enable_stereo
        ? 'bg-gray-400 cursor-not-allowed'
        : 'bg-blue-600 hover:bg-blue-700'
    }`}
    onClick={() => handleStartCalibration(MenuActions.CALIBRATE_STEREO)}
    disabled={isCalibrating || !systemConfig.stereo_vision?.enable_stereo}
    title={
      !systemConfig.stereo_vision?.enable_stereo
        ? 'Enable Stereo Vision in Settings to calibrate dual cameras'
        : 'Launch single-sweep stereo calibration'
    }
  >
    6. Stereo Vision Calibration
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
- **Dual Camera Video Streaming:**
  During `CALIBRATE_STEREO`, the camera viewport renders side-by-side video feeds (`/video_feed?camera=left` and `/video_feed?camera=right`) to allow verifying marker visibility in both camera streams simultaneously.
- **AR Verification Preview:** Renders real-time 3D wireframe box preview over detected physical tokens upon completion.

### 5.3 Settings & Configuration Controls (`SettingsModal.tsx` & `ConfigurationSidebar.tsx`)

- Renders metadata-driven form controls for `stereo_vision` fields (`baseline_separation_mm`, camera device path dropdowns, enable toggle) bound directly to `useSystemState()`.

______________________________________________________________________

## 6. Verification Criteria

- [ ] `CameraDeviceSchema` and `StereoVisionConfigSchema` maintained in `config_schema.py` and embedded in `GlobalConfigSchema`.
- [ ] `scripts/generate_ts_schema.py` imports schemas and executes cleanly, updating `schema.generated.ts`.
- [ ] `MenuActions.CALIBRATE_STEREO` and `SceneId.CALIBRATE_STEREO` defined in backend `common_types.py` and frontend `system.ts`.
- [ ] `SceneManager.transition_to()` records `SceneId` value in `_scene_atom` for consistent frontend state reflection.
- [ ] Tabletop hierarchical menu (`menu_builder.py` and `menu_scene.py`) contains `"6. Stereo Vision Calibration"` and transitions to `SceneId.CALIBRATE_STEREO`.
- [ ] Action Dispatcher handles `CALIBRATE_STEREO` with defensive guards against disabled stereo configuration.
- [ ] `PersistenceService.save_stereo_calibration()` serializes `stereo_calibration.json` and updates `GlobalConfig` atomically.
- [ ] `CalibrationWizard.tsx` includes `"6. Stereo Vision Calibration"` button (disabled when stereo is off), dual-feed rendering, and instructions card.
- [ ] `StereoVisionDashboard.tsx` renders dual camera feeds and live diagnostic metrics.
