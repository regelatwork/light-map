# Feature: Refactor InteractiveApp (Decoupling & State Management)

## Problem Statement

The `InteractiveApp` class has become a "God Object," violating the Single Responsibility Principle. It currently manages:
- Application State (Modes: Menu, Map, Calibration, Scanning, etc.)
- Input Routing & Gesture Interpretation
- Rendering Orchestration
- Computer Vision Logic (Token Scanning, Calibration)
- Configuration Management

This results in:
- **High Complexity**: `process_frame` and `render` methods are dominated by large `if/elif` blocks checking `self.mode`.
- **State Pollution**: The `__init__` method initializes dozens of variables specific to transient modes (e.g., `calib_flash_stage`, `scan_stage`), keeping them in memory even when not needed.
- **Code Duplication**: Logic for map interaction (pan/zoom) is duplicated between `MapMode` and `CalibMapGridMode`.
- **Testability Issues**: Testing a specific mode requires instantiating the entire `InteractiveApp`.

## Proposed Solution: Scene-Based Architecture

We will refactor the application to use a **State Pattern** (or Scene Graph) approach. The `InteractiveApp` will act as a **Scene Manager**, delegating logic to discrete `Scene` objects.

### 1. Core Abstractions

#### Directory Structure
```
src/light_map/
├── core/
│   ├── app_context.py       # AppContext, shared services
│   ├── scene.py             # Scene ABC, SceneAction, HandInput
│   └── notification.py      # NotificationManager
├── scenes/
│   ├── menu_scene.py
│   ├── map_scene.py
│   ├── calibration_scenes.py
│   └── ...
└── interactive_app.py       # Main Loop & SceneManager
```

#### `HandInput` (Standardized Input)
A dataclass to decouple logic from raw MediaPipe dictionaries.
```python
@dataclass
class HandInput:
    gesture: GestureType
    proj_pos: Tuple[int, int]  # (x, y) in projector space
    raw_landmarks: Any         # MediaPipe landmarks
```

#### `SceneAction` (Transition Protocol)
Defines how a scene requests a state change.
```python
@dataclass
class SceneTransition:
    target_scene: Type['Scene']  # or Enum if preferred, but Class is flexible
    payload: Any = None          # e.g., map filename
    reset_history: bool = False  # Clear stack?
```

#### `AppContext`
A shared data container passed to all scenes.
```python
@dataclass
class AppContext:
    config: AppConfig
    map_system: MapSystem
    map_config: MapConfigManager
    projector_matrix: np.ndarray
    notifications: NotificationManager
    # ... other shared services
```

#### `Scene` (Abstract Base Class)
```python
class Scene(ABC):
    def __init__(self, ctx: AppContext):
        self.ctx = ctx

    def on_enter(self, payload: Any = None):
        """Called when the scene becomes active."""
        pass

    def on_exit(self):
        """Called when the scene is deactivated."""
        pass

    def update(self, inputs: List[HandInput], current_time: float) -> Optional[SceneTransition]:
        """Processes input and returns a transition request (if any)."""
        pass

    def render(self, frame: np.ndarray) -> np.ndarray:
        """Renders the scene's visual output. Returns the modified frame."""
        pass
```

### 2. Global Overlay & Debug Strategy

`InteractiveApp` will retain responsibility for the final composite render to ensure critical info is always visible.

**Pseudo-code for `InteractiveApp.process_frame`:**
```python
def process_frame(self, frame, results):
    # 1. Standardize Input
    inputs = self._convert_mediapipe_to_inputs(results)
    
    # 2. Scene Update
    transition = self.current_scene.update(inputs, time.time())
    if transition:
        self._switch_scene(transition)

    # 3. Scene Render
    scene_frame = self.current_scene.render(frame)

    # 4. Global Overlays (Debug, Notifications, FPS)
    final_frame = self._render_global_overlays(scene_frame)
    
    return final_frame
```

### 3. Concrete Scenes & Logic

| Current Mode | New Scene Class | Responsibilities |
| :--- | :--- | :--- |
| `AppMode.MENU` | `MenuScene` | Manages `MenuSystem`. **Crucial**: Translates string actions (e.g., `"LOAD_MAP|file"`) into `SceneTransition(MapScene, payload="file")`. |
| `AppMode.VIEWING` | `ViewingScene` | Read-only map view. |
| `AppMode.MAP` | `MapScene` | Uses `MapInteractionController` for Pan/Zoom. |
| `AppMode.SCANNING` | `ScanningScene` | Controls Flash -> Capture sequence. |
| `AppMode.CALIB_*` | `Calibration*Scene` | Specific calibration flows. |

#### `MapInteractionController`
A helper class to centralize pan/zoom math, used by both `MapScene` and `CalibrationGridScene`.
```python
class MapInteractionController:
    def process_gestures(self, inputs: List[HandInput], map_system: MapSystem, current_time: float) -> bool:
        # Returns True if interaction occurred (pan/zoom)
        # Handles 2-hand zoom math and 1-hand pan math
        pass
```

## Refactoring Plan

### Phase 1: Infrastructure
- [ ] Create `src/light_map/core/` and define `AppContext`, `HandInput`, `Scene`, `SceneTransition`.
- [ ] Implement `NotificationManager` (simple list of timestamped messages).
- [ ] Implement `MapInteractionController` and move pan/zoom logic there.

### Phase 2: Incremental Extraction
- [ ] **Step 1**: Extract `MenuScene`. Implement the "Translation Layer" for menu actions.
- [ ] **Step 2**: Extract `ScanningScene` and `FlashCalibrationScene` (High state pollution).
- [ ] **Step 3**: Extract `MapScene` and `ViewingScene` using `MapInteractionController`.
- [ ] **Step 4**: Extract remaining Calibration scenes.

### Phase 3: Cleanup
- [ ] Update `InteractiveApp` to use `SceneManager` logic.
- [ ] Remove `AppMode` enum and old state variables from `InteractiveApp`.

## Testing Strategy

### 1. Unit Tests (New)
- **`MapInteractionController`**: Test pan/zoom math with deterministic `HandInput` lists. No mocking of global app state needed.
- **`MenuScene`**: Test that specific menu action strings correctly produce the expected `SceneTransition` objects.
- **`ScanningScene`**: Test the state machine transitions (Init -> Flash -> Capture -> Result) by calling `update()` with mocked time increments.

### 2. Integration Tests
- **Scene Switching**: Verify `InteractiveApp` correctly calls `on_exit` on the old scene and `on_enter` on the new one during a transition.
- **Input Pipeline**: Verify that raw MediaPipe results are correctly converted to `HandInput` objects with correct coordinate transforms.

### 3. Missing/New Test Cases
- **`test_map_interaction_controller.py`**:
    - `test_zoom_scaling`: Verify 2-hand distance change produces correct zoom factor.
    - `test_pan_delta`: Verify 1-hand movement produces correct pan delta.
- **`test_menu_scene.py`**:
    - `test_action_load_map`: Triggering "LOAD_MAP|test.svg" returns `SceneTransition(MapScene, payload="test.svg")`.
- **`test_scene_manager.py`**:
    - `test_context_persistence`: Verify `AppContext` data (like loaded map) persists across scene changes.
