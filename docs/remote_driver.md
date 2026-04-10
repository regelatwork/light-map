# Remote Application Driver & Web Dashboard

The Remote Application Driver provides a REST API and WebSocket stream to control the Light Map application, inspect its internal state, and serve the **Light Map Control Dashboard**.

## 1. Web Dashboard

The easiest way to interact with the system remotely is through the built-in web dashboard. It provides a visual "Schematic View" of the tabletop, real-time token tracking, and interactive calibration wizards.

### Accessing the Dashboard

While the Light Map application is running, navigate to the following URL in any modern web browser:

`http://127.0.0.1:8000` (or the IP address of the machine running the app)

### Key Features

- **Schematic View**: A live SVG-based representation of the map, grid, and tokens.
- **Calibration Wizards**: Step-by-step UI for Camera Intrinsics, Projector Homography, and PPI calibration.
- **Asset Library**: Browse and load SVG maps directly from the UI.
- **Configuration Sidebar**: Adjust grid offsets and token properties with live preview.
- **Vision Control**: Toggle "Exclusive Vision" and "Hand/Token Masking" modes.

______________________________________________________________________

## 2. Starting the Driver

The driver is integrated into the main application and can be enabled using CLI flags.

### CLI Flags

| Flag | Description | Values |
| :--- | :--- | :--- |
| `--remote-hands` | Remote hand input mode | `exclusive`, `merge`, `ignore` (default) |
| `--remote-tokens` | Remote token input mode | `exclusive`, `merge`, `ignore` (default) |
| `--remote-host` | Host address for the HTTP API | String (default: `127.0.0.1`) |
| `--remote-port` | Port for the HTTP API | Integer (default: `8000`) |
| `--remote-origins` | Allowed CORS origins | Space-separated list (default: localhost/127.0.0.1 on 8000/5173) |

### CORS Security

For security, the Remote Driver restricts Cross-Origin Resource Sharing (CORS) to specific origins. By default, it allows:

- `http://localhost:8000` and `http://127.0.0.1:8000` (The dashboard)
- `http://localhost:5173` and `http://127.0.0.1:5173` (Vite development server)

If you are accessing the API from a different origin (e.g., a custom web app on another server or another machine on the network), you must specify the allowed origins using the `--remote-origins` flag:

```bash
python3 -m light_map --remote-hands merge --remote-origins http://my-frontend.local http://192.168.1.50:3000
```

### Example Usage

Start with exclusive remote hand control (disables physical camera for hands):

```bash
python3 -m light_map --remote-hands exclusive
```

Start with merged control (both physical camera and remote API are active):

```bash
python3 -m light_map --remote-hands merge --remote-tokens merge
```

## 2. API Reference

By default, the API is available at `http://127.0.0.1:8000` (can be changed with `--remote-host` and `--remote-port`).

### 2.1 Input Injection (POST)

These endpoints allow you to "mock" physical interactions.

#### `POST /input/hands`

Injects virtual hand gestures at specific projector (screen) coordinates.

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

#### `POST /input/hands/world`

Injects virtual hand gestures at specific **world (map) coordinates**. The application automatically translates these to projector coordinates using the current viewport.

**Payload Schema:**

```json
[
  {
    "world_x": 100.5,
    "world_y": 200.5,
    "gesture": "Pointing"
  }
]
```

**Example (`curl`):**

```bash
curl -X POST http://127.0.0.1:8000/input/hands/world \
     -H "Content-Type: application/json" \
     -d '[{"world_x": 10.0, "world_y": 10.0, "gesture": "Pointing"}]'
```

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

#### `POST /map/zoom`

Injects a zoom action for the map system.

#### `POST /config/viewport`

Directly sets the map's zoom, pan, and rotation.

**Payload Schema:**

```json
{
  "zoom": 1.0,
  "pan_x": 0.0,
  "pan_y": 0.0,
  "rotation": 0.0
}
```

- All fields are optional.

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

- **Enhanced Fields:** Includes `screen_x` and `screen_y` (projector coordinates) for every token, allowing remote drivers to target tokens with virtual hands.

#### `GET /state/blockers`

Returns the current visibility geometry (doors, walls) loaded from the SVG. Useful for determining target coordinates for testing.

#### `GET /state/dwell`

Exposes the internal state of the interaction `DwellTracker`.

- **Fields:** `accumulated_time`, `is_triggered`, `last_point`, `target_id`.

#### `GET /state/logs`

Retrieves the most recent application logs.

- **Query Param:** `lines` (default: 100).

#### `GET /state/clock`

Returns the application's current `time.monotonic()` value.

- **Benefit:** Allows remote clients to synchronize their internal timers with the application logic.

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
