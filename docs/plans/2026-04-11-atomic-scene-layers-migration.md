# Plan: Fully Migrate Legacy Scenes to the Atomic Layer System (Junior-Ready)

This plan describes the final phase of the rendering refactor: eliminating the `SceneLayer` / `LegacySceneLayer` bridge and replacing it with specialized, data-driven `Layer` implementations for each scene type.

## Objective

1.  **Eliminate the `SceneLayer` bridge:** Remove the pattern where a generic layer delegates rendering to a monolithic `Scene.render()` method.
2.  **Scene-Specific Layers:** Implement dedicated layers (`CalibrationLayer`, `FlashLayer`, `MapGridLayer`) that consume granular `WorldState` atoms and return `ImagePatch`es directly.
3.  **Refactor Scenes to Controllers:** Transition existing `Scene` objects to be pure "Controllers" that handle logic and update `WorldState`, with no rendering responsibility.
4.  **Granular Versioning:** Ensure that only the necessary parts of the screen are re-rendered when a scene's state changes.

## Architectural Direction

All rendering logic must move from `Scene.render()` (OpenCV-heavy) to `Layer._generate_patches()`.
- **Scenes** (e.g., `ExtrinsicsCalibrationScene`) now only manage state transitions, gesture handling, and updating `self.context.state.calibration`.
- **Layers** (e.g., `CalibrationLayer`) observe `state.calibration_version` and draw based on the current `stage`, `target_status`, etc.

## Detailed Interfaces & File Locations

### 1. `src/light_map/state/world_state.py` (Atoms)

Update the `CalibrationState` dataclass in `src/light_map/core/common_types.py` to include:
```python
@dataclass
class CalibrationState:
    stage: str = ""
    target_status: List[str] = field(default_factory=list)
    target_info: List[Dict[str, Any]] = field(default_factory=list)
    reprojection_error: float = 0.0
    animation_start_times: Dict[int, float] = field(default_factory=dict)
    last_camera_frame_ts: int = 0
    captured_count: int = 0
    total_required: int = 0
    candidate_ppi: float = 0.0
    step_index: int = 0
    # ADDED FOR MIGRATION:
    flash_intensity: int = 0
    instruction_text: str = ""
    instruction_pos: Tuple[int, int] = (50, 50)
    pattern_image: Optional[np.ndarray] = None  # Homography pattern
    # For Extrinsics residuals:
    object_points: Optional[np.ndarray] = None
    image_points: Optional[np.ndarray] = None
    rotation_vector: Optional[np.ndarray] = None
    translation_vector: Optional[np.ndarray] = None
```

### 2. New Layer Implementations

#### `FlashLayer` in `src/light_map/rendering/layers/flash_layer.py`
```python
class FlashLayer(Layer):
    def __init__(self, state: WorldState, width: int, height: int):
        super().__init__(state=state, is_static=True, layer_mode=LayerMode.BLOCKING)
        self.width = width
        self.height = height

    def get_current_version(self) -> int:
        return self.state.calibration_version

    def _generate_patches(self, current_time: float) -> List[ImagePatch]:
        intensity = self.state.calibration.flash_intensity
        img = np.full((self.height, self.width, 3), intensity, dtype=np.uint8)
        return [ImagePatch(0, 0, self.width, self.height, img)]
```

#### `MapGridLayer` in `src/light_map/rendering/layers/map_grid_layer.py`
```python
class MapGridLayer(Layer):
    def __init__(self, state: WorldState, width: int, height: int):
        super().__init__(state=state, is_static=False, layer_mode=LayerMode.NORMAL)
        self.width = width
        self.height = height

    def get_current_version(self) -> int:
        return self.state.grid_metadata_version

    def _generate_patches(self, current_time: float) -> List[ImagePatch]:
        # Logic: Move MapGridCalibrationScene.render crosses logic here.
        # Use self.state.grid_metadata.spacing_svg * current_zoom for spacing.
        # Draw crosses at (origin_x + i*spacing, origin_y + j*spacing).
```

#### `CalibrationLayer` in `src/light_map/rendering/layers/calibration_layer.py`
```python
class CalibrationLayer(Layer):
    def __init__(self, state: WorldState, width: int, height: int):
        super().__init__(state=state, is_static=False, layer_mode=LayerMode.BLOCKING)
        self.width = width
        self.height = height

    def get_current_version(self) -> int:
        return max(self.state.calibration_version, self.state.system_time_version)

    def _generate_patches(self, current_time: float) -> List[ImagePatch]:
        cal = self.state.calibration
        # 1. Start with pattern_image if present, else SCENE_BG_COLOR.
        # 2. Draw Target Zones (rects/labels) from target_status.
        # 3. Draw Reprojection Residuals if stage == "VALIDATION".
        # 4. Draw expanding circle animations using current_time vs animation_start_times.
        # 5. Draw instruction_text at instruction_pos.
```

## Phase 1 Checklist: Infrastructure & Map Grid (Junior-Friendly)

- [ ] **Task 1: Update State Model.** In `src/light_map/core/common_types.py`, add the new fields to `CalibrationState` (flash_intensity, instruction_text, etc.).
- [ ] **Task 2: Define FlashLayer.** Create `src/light_map/rendering/layers/flash_layer.py` and implement the `FlashLayer` class as specified above.
- [ ] **Task 3: Define MapGridLayer.** Create `src/light_map/rendering/layers/map_grid_layer.py`. Port the cross-drawing logic from `MapGridCalibrationScene.render` into `_generate_patches`.
- [ ] **Task 4: Register Layers.** In `src/light_map/core/layer_stack_manager.py`, import the new layers and initialize `self.flash_layer`, `self.map_grid_layer`, and `self.calibration_layer` in `__init__`.
- [ ] **Task 5: Refactor MapGrid Scene (Logic).** In `src/light_map/calibration/calibration_scenes.py`, remove the `render()` method from `MapGridCalibrationScene`.
- [ ] **Task 6: Refactor MapGrid Scene (State).** Ensure `MapGridCalibrationScene.update` pushes the current grid overlay coordinates into `self.context.state.grid_metadata` (this triggers the layer to re-render).
- [ ] **Task 7: Update Layer Stack Selection.** Update `MapGridCalibrationScene.get_active_layers` to return `[app.map_layer, app.map_grid_layer, app.token_layer, ...]`. Note the replacement of `app.scene_layer` with `app.map_grid_layer`.
- [ ] **Task 8: Verify Map Grid.** Run the app, enter Map Grid Calibration, and ensure the grid crosses appear and move correctly as you pan/zoom.
- [ ] **Task 9: Fix Imports.** Run `ruff check src/light_map/` to ensure no circular imports were introduced (especially when adding types to `WorldState`).
- [ ] **Task 10: Unit Test.** Create `tests/test_map_grid_layer.py` and verify it generates the expected number of patches.

## Phase 2 Checklist: Calibration & Flash

- [ ] **Task 1: Define CalibrationLayer.** Create `src/light_map/rendering/layers/calibration_layer.py`. Port the instructions and target drawing logic from `ExtrinsicsCalibrationScene.render`.
- [ ] **Task 2: Migrate Flash Calibration.**
    - Remove `FlashCalibrationScene.render`.
    - Update `FlashCalibrationScene._change_stage` to set `state.calibration.flash_intensity`.
    - Update `FlashCalibrationScene.get_active_layers` to use `app.flash_layer`.
- [ ] **Task 3: Migrate PPI Calibration.** Update `PpiCalibrationScene` to use `CalibrationLayer` for its text feedback.
- [ ] **Task 4: Migrate Intrinsics & Projector.** Update these scenes to use `CalibrationLayer`.

## Phase 3: The "Big One" (Extrinsics)
- Refactor `ExtrinsicsCalibrationScene` to be a pure controller.
- Move its complex residual drawing and animation logic into `CalibrationLayer`.
- Ensure `state.calibration.object_points` etc. are populated after `calibrate_extrinsics` succeeds.

## Phase 4: Cleanup
- [ ] Remove `src/light_map/rendering/layers/legacy_scene_layer.py`.
- [ ] Remove `src/light_map/rendering/layers/scene_layer.py`.
- [ ] Update `LayerStackManager` to remove these layers from the default stack.
- [ ] Final check: Ensure no class in `src/light_map/calibration/` has a `render()` method.

## Verification Plan

### Automated Tests
- `pytest tests/test_map_grid_layer.py`
- `pytest tests/test_calibration_layer.py`
- `pytest tests/test_interactive_app_layered.py`

### Manual Verification
- Run "Step 1: Flash Intensity" and verify the screen flashes correctly.
- Run "Step 5: Extrinsics" and verify targets turn green and animations play when tokens are detected.
- Observe `total_render_logic` in debug overlay (F3).
