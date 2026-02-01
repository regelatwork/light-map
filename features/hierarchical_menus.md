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
The system is divided into five components:
*   **Configuration (`MenuConfig`):** Defines constants, colors, font settings, and the declarative menu structure.
    *   **Gesture Mapping:** Explicitly defines:
        *   `SELECT_GESTURE = GestureType.CLOSED_FIST`
        *   `SUMMON_GESTURE = GestureType.VICTORY`
    *   **Resolution Agnostic:** Does **not** hardcode resolution.
*   **Input Handling (`InputManager`):** Abstracts raw detection into stable input events.
    *   **Responsibility:** Takes raw MediaPipe results + timestamp and returns a stable `(x, y, gesture)` tuple.
    *   **Sticky Hand Strategy:** Tracks a `primary_hand_id`. If `multi_handedness` returns a label (Left/Right), stick to the first detected label.
    *   **Flicker Recovery:** If the primary hand is lost, do NOT immediately clear `primary_hand_id`. Wait for a short timeout (e.g., 0.5s). If the hand reappears within this window, resume tracking. This prevents menu closure during brief tracking failures.
*   **Logic (`MenuSystem`):** Manages hierarchical navigation (stack), state, input smoothing, hit-testing, geometry calculation (layout), and priming/cooldown logic.
    *   **Coordinate Space:** Explicitly uses **Projector Space Pixels** (0,0 to W,H). It **does not** perform coordinate transformations; it expects pre-transformed coordinates.
    *   **Safety:** Incoming coordinates must be **Clamped** to screen boundaries (0, 0, W, H) immediately. The `MenuSystem` is the authoritative source for clamping.
    *   **Resolution Awareness:** Must be initialized with `resolution=(width, height)` to perform correct layout calculations.
*   **Rendering (`MenuRenderer`):** Statelessly draws the menu based on the snapshot. **Does not calculate layout.**
    *   **Text Safety:** Must implement text fitting. If a title exceeds its box width, it must either scale down the font or truncate the text.
*   **Integration (`hand_tracker.py`):** Feeds input to Logic (handling multi-hand resolution), passes output to Renderer, and executes returned Action IDs.
    *   **Resolution Discovery:** `hand_tracker.py` is responsible for establishing the **Single Source of Truth** for resolution.
        *   It MUST load the resolution from `projector_calibration.npz`.
        *   **Backward Compatibility:** It must support legacy `projector_calibration.npz` files that only contain the matrix. If `resolution` is missing from the file, it must fallback to a safe default (e.g., 1280x720) or log a warning and prompt for re-calibration while continuing.
        *   **File Missing Check:** If `projector_calibration.npz` does not exist, it must print a clear error and exit.
        *   **Runtime Verification (with Fallback):** Attempt to verify resolution using `cv2.getWindowImageRect`.
            *   **Risk:** On Linux/Wayland, this often returns `(0,0)` or includes decorations.
            *   **Mitigation:** If `getWindowImageRect` returns valid dimensions matching calibration -> OK. If it returns `(0,0)` or weird values -> Log a warning "Could not detect window size, assuming calibration match" and proceed using the calibrated values. Do NOT crash. Only fail if it returns a valid *but different* resolution.
    *   **Transformation Responsibility:** `hand_tracker.py` MUST perform the explicit coordinate pipeline (Normalized -> Camera -> Projector -> Clamped).
    *   **Action Dispatching:** Maintains an `ActionRegistry` (Command Pattern) mapping `MenuActions` enum values to callables (e.g., `{MenuActions.EXIT: sys.exit}`).
        *   **Defensive Execution:** To prevent crashes from configuration typos or missing implementations, the dispatcher MUST NOT assume the key exists. It should use `registry.get(action_id)` and log a warning if the action is missing, or wrap execution in a broad `try-except` block to catch runtime failures in the called action. This prevents a giant if/elif block while maintaining stability.
    *   **State Ownership:** `hand_tracker.py` owns the runtime state (e.g., `debug_mode` boolean). It injects this state into the `MenuRenderer` via an `external_states` dictionary (e.g., `{MenuActions.TOGGLE_DEBUG: is_debug}`).

### 3. Data Structures

#### Common Types
Defined in `src/light_map/common_types.py`. This prevents circular dependencies.

```python
from enum import StrEnum
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

class GestureType(StrEnum):
    OPEN_PALM = "Open Palm"
    CLOSED_FIST = "Closed Fist"
    # ... other gestures

class MenuActions(StrEnum):
    TOGGLE_DEBUG = "TOGGLE_DEBUG"
    EXIT = "EXIT"
    CALIBRATE = "CALIBRATE"
    NAV_BACK = "NAV_BACK"

@dataclass
class MenuItem:
    title: str
    action_id: Optional[str] = None  # Leaf if set
    children: List['MenuItem'] = field(default_factory=list) # Node if set
    should_close_on_trigger: bool = True
    # NOTE: 'toggled' state is NOT stored here. It is immutable config.
```

#### MenuColors
Defined in `src/light_map/menu_config.py`.
```python
@dataclass
class MenuColors:
    NORMAL: Tuple[int, int, int] = (255, 255, 255) # White
    HOVER: Tuple[int, int, int] = (0, 255, 255)    # Yellow
    # Add others as needed
```

#### MenuState (DTO)
A snapshot returned by `MenuSystem.update()`.
```python
@dataclass
class MenuState:
    current_menu_title: str
    active_items: List[MenuItem]
    item_rects: List[Tuple[int, int, int, int]] # (x, y, w, h)
    hovered_item_index: int | None
    prime_progress: float (0.0 to 1.0)
    summon_progress: float (0.0 to 1.0)
    just_triggered_action: str | None
    cursor_pos: Tuple[int, int] | None
    is_visible: bool
```

### 4. Logic & Interaction (`MenuSystem`)

*   **Initialization:**
    *   `__init__(self, width, height, root_item, time_provider=time.monotonic)`
    *   **Dependency Injection:** Accepts a `time_provider` callable returning a float. This allows unit tests to inject a deterministic clock (e.g., lambda: mock_time).
    *   **Buffer Calculation:** `maxlen` MUST be calculated dynamically.
        *   `maxlen = int(TARGET_FPS * LOCK_DELAY * 2)`
        *   Example: 60 FPS * 0.3s * 2 = 36 frames. Round up to 40 to be safe.

*   **Visibility & Summoning:**
    *   Internal State Machine: `HIDDEN`, `SUMMONING`, `WAITING_FOR_NEUTRAL`, `ACTIVE`.
    *   **Neutral State Requirement:** After summoning, ignore selection gestures until an "Open Palm" (or neutral) is seen to prevent accidental immediate clicks.

*   **Navigation Logic:**
    *   **Back Button Injection:** When entering a submenu, create a **new list** of items. **Insert** a generated `MenuItem(title="< Back", action_id=MenuActions.NAV_BACK)` at **index 0** (the top) for muscle memory consistency. Never modify the configuration objects.
    *   **Back Button Priority:** The "Back" button is exempt from displacement by the overflow logic; it MUST always be visible if the current menu is a submenu.

*   **Input Smoothing & Stability:**
    *   **History Buffer:** Store `(timestamp, pos)` tuples using a `collections.deque` with a fixed `maxlen`. This provides O(1) appends and is efficient for iteration.
    *   **Cursor Tracking Strategy ("Pinning"):**
        *   When `gesture` transitions to `SELECT_GESTURE`, calculate `lock_time = current_time - LOCK_DELAY`.
        *   Iterate the deque **backwards** to find the **first** entry where `entry_timestamp <= lock_time`.
        *   Lock cursor to that historical position.
        *   If the buffer is too short or no such entry exists, use the oldest available point in the deque.
    *   **Debouncing (Grace Period):**
        *   If `SELECT_GESTURE` is lost (but hand position is valid), wait `GRACE_PERIOD` (0.2s) before resetting the prime timer.

*   **Layout Mathematics:**
    *   **Vertical Layout:** Centered vertically based on total content height.
    *   **Horizontal Layout:** Centered horizontally. `item_width = screen_width * ITEM_WIDTH_PCT`.
    *   **Constraints:** Enforce max items (e.g., 5).
    *   **Overflow Behavior:** If `len(items) > max_items`, render the first `max_items - 1` items. The last slot is reserved for a non-interactive "..." item. A warning must be logged. This prevents UI breaks or crashes.

### 5. Visual Design (`MenuRenderer`)
*   **External State Injection:**
    *   `render` method accepts `external_states: Dict[str, bool]`.
    *   Use this to determine if a toggleable item is "Active" (e.g., green checkbox).
*   **Text Safety:**
    *   Calculate text width using `cv2.getTextSize`.
    *   If `text_width > box_width`:
        *   Option A: Reduce `font_scale` proportionally.
        *   Option B: Truncate text with ellipsis (e.g., "CALIBRAT...").
        *   *Recommendation:* Try scaling down to 70% min, then truncate.

## Implementation Plan

### Phase 0: Shared Types & Configuration
**Goal:** Establish common vocabulary and prevent circular imports.

*   **File:** `src/light_map/common_types.py`
*   **Tasks:**
    1.  Define `GestureType` (StrEnum), `MenuActions` (StrEnum), and `MenuItem` (Dataclass).
*   **File:** `src/light_map/menu_config.py`
*   **Tasks:**
    1.  Import types from `common_types`.
    2.  Define constants (`LOCK_DELAY`, `EMA_ALPHA`, etc.).
    3.  Define the menu structure.

### Phase 0.5: Persistence Infrastructure (New Feature)
**Goal:** Implement robust calibration saving/loading with backward compatibility.

*   **Files:** `projector_calibration.py`, `hand_tracker.py`
*   **Tasks:**
    1.  **Update `projector_calibration.py`:**
        *   Modify the saving logic to include `resolution` (and `camera_calibration.npz` data if applicable) in `projector_calibration.npz`.
        *   Use `numpy.savez(..., resolution=np.array([w, h]))`.
    2.  **Refactor `hand_tracker.py` Loader:**
        *   **Migration Strategy:** The loader MUST be robust. Implement a `try-except` or `if 'resolution' in data` check.
        *   If `resolution` is missing (legacy file), log a warning: `"Legacy calibration detected. Using fallback resolution (1280x720). Please re-run projector_calibration.py to optimize."`
        *   Ensure the tool remains functional with old calibration files to avoid breaking the current working state.
        *   Implement **Graceful Fallback** for resolution verification (Log warning on mismatch/failure, don't crash unless critical).

### Phase 0.8: Input Abstraction
**Goal:** Testable input handling.

*   **File:** `src/light_map/input_manager.py`
*   **Tasks:**
    1.  Implement `InputManager` class.
    2.  Implement "Sticky Hand" logic and "Flicker Recovery" within `InputManager`.
    3.  **Unit Tests:** Verify `primary_hand_id` retention during brief gaps using mocked timestamps.

### Phase 1: Core Logic
**Goal:** Testable state machine.

*   **File:** `src/light_map/menu_system.py`
*   **Tasks:**
    1.  Implement `__init__` with `time_provider` injection.
    2.  Implement buffer with calculated `maxlen`.
    3.  Implement "Pinning" with backwards search.
    4.  Implement State Machine (`HIDDEN` -> `ACTIVE`).
    5.  Implement Layout overflow handling (MAX-1 + "...").
    6.  **Unit Tests:** Verify pinning and state transitions without CV2, utilizing injected `time_provider` for deterministic time travel.

### Phase 2: Renderer
**Goal:** Safe rendering.

*   **File:** `src/light_map/menu_renderer.py`
*   **Tasks:**
    1.  Implement `render(state, external_states)`.
    2.  Implement text fitting logic (scale/truncate).

### Phase 3: Integration
**Goal:** Wiring it up.

*   **File:** `hand_tracker.py`
*   **Tasks:**
    1.  Instantiate `InputManager` to handle hand tracking logic.
    2.  Implement `ActionRegistry` dictionary map.
    3.  **Defensive Dispatcher:** Implement the logic to execute actions via `registry.get(action_id, noop)` or with error handling to prevent crashes on missing keys.
    4.  Inject `external_states` (debug mode).
    5.  Connect input/output loop.