# Remote Application Driver (Light-Map WebDriver)

The Remote Application Driver provides a REST API to control the Light Map application and inspect its internal state. This is primarily used for automated testing, remote diagnostics, and distributed control.

## 1. Starting the Driver

The driver is integrated into `hand_tracker.py` and can be enabled using CLI flags.

### CLI Flags

| Flag | Description | Values |
| :--- | :--- | :--- |
| `--remote-hands` | Remote hand input mode | `exclusive`, `merge`, `ignore` (default) |
| `--remote-tokens` | Remote token input mode | `exclusive`, `merge`, `ignore` (default) |
| `--remote-port` | Port for the HTTP API | Integer (default: `8000`) |

### Example Usage

Start with exclusive remote hand control (disables physical camera for hands):

```bash
python3 hand_tracker.py --remote-hands exclusive
```

Start with merged control (both physical camera and remote API are active):

```bash
python3 hand_tracker.py --remote-hands merge --remote-tokens merge
```

## 2. API Reference

By default, the API is available at `http://127.0.0.1:8000`.

### 2.1 Input Injection (POST)

These endpoints allow you to "mock" physical interactions.

#### `POST /input/hands`

Injects virtual hand gestures at specific projector coordinates.

**Payload Schema:**

```json
[
  {
    "x": 100,
    "y": 200,
    "gesture": "Pointing"
  }
]
```

- `gesture` options: `Pointing`, `Open Palm`, `Closed Fist`, `Gun`, `Victory`, `Rock`, `Shaka`, `None`.

**Example (`curl`):**

```bash
curl -X POST http://127.0.0.1:8000/input/hands 
     -H "Content-Type: application/json" 
     -d '[{"x": 500, "y": 500, "gesture": "Pointing"}]'
```

#### `POST /input/tokens`

Injects virtual ArUco tokens into the map system.

**Payload Schema:**

```json
[
  {
    "id": 42,
    "x": 10.5,
    "y": 20.7,
    "z": 0.0,
    "angle": 45.0
  }
]
```

- `x`, `y`: World coordinates (usually in mm or SVG units depending on calibration).

**Example (`curl`):**

```bash
curl -X POST http://127.0.0.1:8000/input/tokens 
     -H "Content-Type: application/json" 
     -d '[{"id": 1, "x": 100.0, "y": 100.0}]'
```

### 2.2 State Inspection (GET)

These endpoints allow you to query the current state of the application.

#### `GET /state/world`

Returns a snapshot of the general world state.

- **Includes:** Current scene, viewport (zoom/pan), and performance metrics (FPS).
- **Note:** The `fps` value returned is the instantaneous frame rate calculated in the main loop.

#### `GET /state/menu`

Returns information about the active menu.

- **Includes:** Menu title, current depth, and a list of active menu item titles.

#### `GET /state/tokens`

Returns the current list of detected tokens (physical and virtual).

#### `GET /config`

Returns the current application configuration.

- **Includes:** Camera/Projector resolutions and active remote modes.

#### `GET /health`

Returns the status of the remote driver process.

## 3. Python Integration Example

You can use the `httpx` or `requests` library to automate interactions. See `scripts/verify_performance.py` for a comprehensive example of automated performance and caching verification.

```python
import httpx
import time

BASE_URL = "http://127.0.0.1:8000"

# 1. Check current menu
resp = httpx.get(f"{BASE_URL}/state/menu")
print(f"Active Menu: {resp.json().get('title')}")

# 2. Trigger a "Click" (Pointing gesture)
httpx.post(f"{BASE_URL}/input/hands", json=[
    {"x": 500, "y": 300, "gesture": "Pointing"}
])

# 3. Simulate a Token appearing
httpx.post(f"{BASE_URL}/input/tokens", json=[
    {"id": 10, "x": 50.0, "y": 50.0}
])
```

## 4. Performance Monitoring and Diagnostics

The Remote Application Driver, when used in conjunction with `--debug` and `--log-level DEBUG`, provides detailed performance telemetry.

### 4.1 Latency Instrumentation

The application tracks various internal intervals (in nanoseconds) and logs statistical reports every 10 seconds. These logs include:

- **`total_render_logic`**: Time spent in the entire `process_state` logic including layer preparation and composition.
- **`renderer_composite`**: Time spent inside the `Renderer.render` call (compositing layers).
- **`shm_wait_main`**: Time the main loop spent waiting for access to the shared camera frame.
- **`queue_transit_to_main`**: Latency of vision results traveling from worker processes to the main loop.

Statistics provided include Average, P50 (Median), P90, and P95 percentiles.

### 4.2 Verifying Caching

To verify that the layered rendering and caching system is working correctly:

1. Start the app with `--log-level DEBUG`.
1. Observe the `RENDER TOTAL` log entries. These should only appear when a re-render is actually triggered by a state change (e.g., token movement, menu interaction).
1. In a stable state (no movement), re-renders should be skipped, and `RENDER TOTAL` should not appear frequently.
1. Check the 10s Performance Statistics for `renderer_composite` and `total_render_logic` to ensure average times stay within acceptable limits for your hardware.

### 4.3 Automated Verification Script

The `scripts/verify_performance.py` script automates the process of:

1. Starting the application with a specific map.
1. Waiting for API readiness.
1. Injecting virtual inputs (tokens, hands) via the Remote Driver.
1. Capturing and verifying the world state changes.
1. Extracting performance statistics from the logs.

Use this script as a template for building your own automated E2E tests and performance regressions.

## 5. Interactive Documentation (Swagger)

Once the application is running, you can access the full interactive API documentation provided by FastAPI:

- **Swagger UI:** `http://127.0.0.1:8000/docs`
- **ReDoc:** `http://127.0.0.1:8000/redoc`
