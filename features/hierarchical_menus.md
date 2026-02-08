# Feature: Hierarchical Menus

## Overview
This feature enables a gesture-controlled hierarchical menu system projected onto the surface. Users can open a menu, navigate through sub-menus, and make selections using specific hand gestures.

**Note:** This feature assumes the system is already calibrated. Handling "Menu-driven Calibration" (entering calibration from the menu when uncalibrated) is out of scope for this iteration.

## Goals
1.  **Hands-free control:** Interface for controlling the application without keyboard/mouse.
2.  **Robust Inputs:** Utilize specific gestures to avoid accidental triggers.
3.  **Safety & Stability:** Implement a "Hold-to-Prime" selection mechanism with hysteresis to prevent accidental clicks.
4.  **Jitter Reduction:** Smooth noisy input signals and handle "cursor jump" during gesture transitions.
5.  **Strict Separation of Concerns:** Logic (`MenuSystem`) calculates ALL state and geometry (layout) in **Projector Space Pixels**; Rendering (`MenuRenderer`) purely draws what it is told.
6.  **Non-Blocking:** Menu actions must not block the main application loop.
7.  **Testability:** Core logic must be testable via unit tests without physical hardware.

## Design

### 1. Standards
*   **Coordinate System:** The origin (0, 0) is the **Top-Left** corner of the projector screen. X increases to the right, Y increases downwards.
*   **Color Space:** All colors are defined as **BGR tuples** (Blue, Green, Red) to match OpenCV defaults. For example, Yellow is `(0, 255, 255)` (0 Blue, 255 Green, 255 Red), not `(255, 255, 0)` (RGB).
*   **Shared Types:** To prevent circular dependencies between configuration, logic, and detection, all shared types (`GestureType`, `MenuItem`, `MenuActions`) MUST be defined in `src/light_map/common_types.py`.

### 2. Architecture
The system is divided into layers to separate hardware I/O from application logic:

#### Layer 1: Hardware & Entry Point (`hand_tracker.py`)
*   **Responsibility:** "God Script" no more. It handles **only** the physical world.
    *   Initializes the Camera (GStreamer/OpenCV).
    *   Initializes the Projector Window (OpenCV `imshow`).
    *   Loads calibration files from disk.
    *   Runs the main `while True` loop.
    *   Passes raw frames to Layer 2.
    *   Displays the final image returned by Layer 2.
    *   Executes high-level system commands (e.g., `sys.exit`) requested by Layer 2.

#### Layer 2: Application Orchestration (`InteractiveApp`)
*   **File:** `src/light_map/interactive_app.py`
*   **Responsibility:** The "Brain" of the application. Testable without a camera.
    *   **State Management:** Holds instances of `MenuSystem`, `InputManager`, and `Renderer`.
    *   **Coordinate Transformation:** Owns the `projector_matrix` and performs `Camera Space -> Projector Space` transformation.
    *   **Data Flow:** Pipes data: `Frame` -> `MediaPipe` -> `InputManager` -> `MenuSystem` -> `Renderer` -> `Output Image`.
    *   **Interface:**
        *   `process_frame(frame, mp_results) -> (output_image, list_of_actions)`
        *   `set_debug_mode(enabled: bool)`
        *   `reload_config(config: AppConfig)`

#### Layer 3: Core Logic Components
*   **Input Handling (`InputManager`):** Abstracts raw detection into stable input events.
    *   **Sticky Hand Strategy:** Tracks a `primary_hand_id`.
    *   **Flicker Recovery:** Handles brief loss of tracking.
*   **Menu Logic (`MenuSystem`):** Manages navigation stack, state machine, and layout calculation.
    *   **Coordinate Space:** Strictly **Projector Space Pixels**.
*   **Rendering (`MenuRenderer`):** Statelessly draws the menu.
*   **Configuration (`MenuConfig`):** Defines constants and declarative menu structure.

### 3. Component Interfaces & Data Structures

#### Shared Types (`src/light_map/common_types.py`)
```python
class GestureType(StrEnum):
    OPEN_PALM = "Open Palm"
    CLOSED_FIST = "Closed Fist"
    # ...

class MenuActions(StrEnum):
    TOGGLE_DEBUG = "TOGGLE_DEBUG"
    EXIT = "EXIT"
    # ...

@dataclass
class MenuItem:
    title: str
    action_id: Optional[str] = None
    children: List['MenuItem'] = ...
```

#### Application Orchestrator (`src/light_map/interactive_app.py`)
```python
@dataclass
class AppConfig:
    width: int
    height: int
    projector_matrix: np.ndarray
    root_menu: MenuItem

class InteractiveApp:
    def __init__(self, config: AppConfig, time_provider=time.monotonic):
        """
        Initialize all sub-components (InputManager, MenuSystem, Renderer).
        """
        pass
        
    def set_debug_mode(self, enabled: bool):
        """Enable/Disable on-screen debug stats and instructions."""
        pass

    def reload_config(self, config: AppConfig):
        """Reloads configuration (e.g. after re-calibration)."""
        pass

    def process_frame(self, frame: np.ndarray, results: Any) -> Tuple[np.ndarray, List[str]]:
        """
        Core loop logic.
        
        Args:
            frame: Raw BGR image from camera.
            results: MediaPipe Hands results object.
            
        Returns:
            output_image: BGR image to be projected (same dims as config.width/height).
            actions: List of action_id strings triggered this frame (e.g., ["EXIT"]).
        """
        pass
```

#### Input Manager (`src/light_map/input_manager.py`)
```python
class InputManager:
    def update(self, x: int, y: int, gesture: GestureType, is_present: bool) -> None:
        """
        Updates internal state with the latest raw input.
        Handles flicker recovery logic internally.
        """
        pass

    def get_x(self) -> int: ...
    def get_y(self) -> int: ...
    def get_gesture(self) -> GestureType: ...
    def is_hand_present(self) -> bool: ...
```

#### Menu System (`src/light_map/menu_system.py`)
```python
@dataclass
class MenuState:
    # ... fields for renderer ...
    just_triggered_action: Optional[str] # The action triggered THIS frame

class MenuSystem:
    def update(self, x: int, y: int, gesture: GestureType) -> MenuState:
        """
        Updates state machine, handles pinning/selection logic, returns snapshot.
        """
        pass
```

### 4. Logic & Interaction Flow

1.  **Hand Tracker (Main Loop):**
    *   Captures `frame`.
    *   Runs `hands.process(frame)`.
    *   Calls `app.process_frame(frame, results)`.
    *   If `actions` contains "EXIT", breaks loop.
    *   Shows `output_image` via `cv2.imshow`.

2.  **Interactive App (`process_frame`):**
    *   Extracts primary hand landmarks.
    *   **Transforms Coordinates:** `cv2.perspectiveTransform(camera_pt, matrix) -> projector_pt`.
    *   Calls `input_manager.update(projector_pt, gesture)`.
    *   Calls `menu.update(input_manager.get_pos(), input_manager.get_gesture())`.
    *   Calls `renderer.render(menu.get_state())`.
    *   Composes final image (Menu on top of black background).
    *   Returns image and any triggered actions.

### 5. Implementation Plan

#### Phase 1: Logic Extraction (Refactoring) [DONE]
**Goal:** Move logic out of `hand_tracker.py` into `InteractiveApp`.

#### Phase 2: Hardware Entry Point Cleanup [DONE]
**Goal:** Simplify `hand_tracker.py`.

#### Phase 3: Testing [DONE]
**Goal:** Verify logic without hardware.

#### Phase 4: Calibration Integration (Refactoring) [DONE]
**Goal:** Integrate calibration as a first-class citizen.