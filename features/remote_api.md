# Feature: Remote Application Driver (Remote API)

## 1. Goal

The Remote Application Driver (Light-Map WebDriver) enables remote control, automated testing, and state introspection of the Light Map application. By providing an HTTP API, it allows external scripts and agents to simulate user inputs (hand gestures, token movements) and query the application's internal state without physical hardware.

## 2. Core Concepts

### 2.1 Process Model

The Remote Driver operates as a dedicated process within the multi-process vision architecture.

- **RemoteDriverProcess**: A separate `multiprocessing.Process` hosting a FastAPI/Uvicorn server.
- **Input Bridge**: Pushes `DetectionResult` objects into the shared `results_queue` used by the `MainLoopController`.
- **State Mirror**: A `multiprocessing.Manager().dict()` provides a shared, synchronized proxy for the Main Process to publish state updates.

### 2.2 Input Policies

Input modes are configured at startup via CLI flags:

- `--remote-hands [exclusive|merge|ignore]`
- `--remote-tokens [exclusive|merge|ignore]`

| Mode | Behavior |
| :--- | :--- |
| **exclusive** | Physical worker is NOT started; only Remote Driver inputs are accepted. |
| **merge** | Both physical worker and Remote Driver push to the queue. |
| **ignore** | Remote Driver inputs for this type are discarded. |

## 3. Technical Specifications

### 3.1 API Endpoints

#### Input Injection (POST)

- `POST /input/hands`: Injects virtual hand landmarks and gestures.
- `POST /input/tokens`: Injects virtual ArUco tokens (ID, world coordinates).

#### State Introspection (GET)

- `GET /config`: Returns `AppConfig` (Resolution, PPI, Distortion Model, Token Config).
- `GET /state/menu`: Returns active menu hierarchy and pixel-perfect bounding boxes.
- `GET /state/world`: Returns a snapshot of `WorldState` (Active Scene, Viewport, Notifications).
- `GET /state/tokens`: Returns currently detected tokens.
- `GET /health`: Returns the status of the remote driver process.

### 3.2 CLI Integration

The driver is integrated into `hand_tracker.py` and managed by the `ProcessManager`.

```bash
python3 hand_tracker.py --remote-hands exclusive --remote-port 8000
```

## 4. Implementation Details

- **Tech Stack**: FastAPI, Uvicorn, Pydantic.
- **Synchronization**: `multiprocessing.Manager().dict()` for the state mirror, updated every tick by the Main Process.
- **Serialization**: Standard JSON.

## 5. Integration Patterns

### 5.1 Automated Scripting (Python)

External scripts can control the application using the `requests` library. This is used for stress testing and regression verification.

### 5.2 Agent Interaction

Agents (like Gemini) can query `/state/menu` to understand the current UI layout and send coordinates for interaction, enabling autonomous operation of the system.

## 6. Verification Plan

### 5.1 Unit Tests

- Verify FastAPI endpoint logic and `DetectionResult` wrapping in `tests/test_remote_driver_logic.py`.

### 5.2 Integration Tests

- Use `pytest` to start the app in `exclusive` mode and verify that `POST` requests trigger the expected `WorldState` mutations in `tests/test_remote_driver_integration.py`.
- Verify `ProcessManager` correctly spawns and cleans up the driver in `tests/test_remote_process_manager.py`.

### 5.3 End-to-End

- Perform "Remote Menu Navigation" tests where a script queries `/state/menu` and sends a `POST /input/hands` "Pointing" gesture to trigger actions.
