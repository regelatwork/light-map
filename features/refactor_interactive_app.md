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

#### `AppContext`
A shared data container passed to all scenes, holding persistent system-wide objects.
```python
@dataclass
class AppContext:
    config: AppConfig
    map_system: MapSystem
    map_config: MapConfigManager
    projector_matrix: np.ndarray
    # ... other shared services
```

#### `Scene` (Abstract Base Class)
The interface for all application states.
```python
class Scene(ABC):
    def __init__(self, context: AppContext):
        self.ctx = context

    def on_enter(self):
        """Called when the scene becomes active."""
        pass

    def on_exit(self):
        """Called when the scene is deactivated."""
        pass

    def update(self, hands_data: List[Dict], current_time: float) -> Optional[SceneAction]:
        """Processes input and returns a transition request (if any)."""
        pass

    def render(self, frame: np.ndarray) -> np.ndarray:
        """Renders the scene's visual output."""
        pass
```

### 2. Concrete Scenes

We will extract the logic from `InteractiveApp` into the following classes:

| Current Mode | New Scene Class | Responsibilities |
| :--- | :--- | :--- |
| `AppMode.MENU` | `MenuScene` | Manages `MenuSystem`, input routing to menu. |
| `AppMode.VIEWING` | `ViewingScene` | Read-only map view, token toggle, summon gesture. |
| `AppMode.MAP` | `MapScene` | Pan, Zoom, Token overlay, persistent map state interactions. |
| `AppMode.SCANNING` | `ScanningScene` | Controls the Flash -> Capture -> Detect -> Result sequence. |
| `AppMode.CALIB_PPI` | `CalibrationPpiScene` | Calibration target detection and PPI confirmation. |
| `AppMode.CALIB_MAP_GRID` | `CalibrationGridScene` | Manual grid alignment (uses logic similar to MapScene). |
| `AppMode.CALIBRATE_FLASH` | `FlashCalibrationScene` | Adaptive flash intensity testing loop. |

### 3. Logic Consolidation

- **InteractionController**: The Pan/Zoom logic currently duplicated can be extracted into a helper class (`MapInteractionController`) used by both `MapScene` and `CalibrationGridScene`.
- **Render Layers**: The `Renderer` class currently mixes UI rendering with Map composition. Scenes should own their specific overlays, while `MapSystem` or `SVGLoader` handles the map background.

## Refactoring Plan

### Phase 1: Infrastructure
- [ ] Define `AppContext` and `Scene` interfaces.
- [ ] Create a `SceneManager` within `InteractiveApp` to handle switching.

### Phase 2: Incremental Extraction
- [ ] **Step 1**: Extract `MenuScene`. This is the most distinct mode.
- [ ] **Step 2**: Extract `ScanningScene` and `FlashCalibrationScene`. These have significant private state (`scan_stage`, `calib_flash_results`) that can be removed from `InteractiveApp`.
- [ ] **Step 3**: Extract `MapScene` and `ViewingScene`.
- [ ] **Step 4**: Extract remaining Calibration scenes.

### Phase 3: Cleanup
- [ ] Remove `AppMode` enum (or keep for serialization if needed, but internal logic should use Classes).
- [ ] Clean up `InteractiveApp` attributes (remove `calib_*`, `scan_*` variables).
- [ ] Consolidate shared logic (e.g., `draw_ghost_tokens` can move to `AppContext` or a helper).

## Benefits

- **Decoupling**: Each scene manages its own state and logic.
- **Memory Efficiency**: Transient state (like calibration results) is created only when the scene is active and discarded on exit.
- **Maintainability**: Adding a new mode (e.g., "Combat Mode") involves creating a new class, not modifying a 500-line `if/elif` block.
- **Testability**: Each `Scene` can be tested in isolation with a mocked `AppContext`.
