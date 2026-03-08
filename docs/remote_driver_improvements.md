# Remote Driver API Improvements

Based on recent debugging sessions involving Exclusive Vision and Door Selection, several gaps in the Remote Driver API were identified. Implementing these enhancements will significantly improve the efficiency of automated testing and remote diagnostics.

## 1. Coordinate System Abstraction

### `POST /input/hands/world`
Currently, hand input requires projector (screen) coordinates. Testing specific world objects (tokens, doors) requires the client to replicate complex matrix transformations (zoom, pan, rotation).
- **Proposed Payload:**
  ```json
  [
    {
      "world_x": 100.0,
      "world_y": 200.0,
      "gesture": "Pointing"
    }
  ]
  ```
- **Benefit:** Allows tests to target map features directly without knowledge of the current viewport state.

### Token Screen Coordinates in `GET /state/tokens`
Include the calculated `screen_x` and `screen_y` for every token in the state response.
- **Benefit:** Allows a remote driver to "follow" a physical token with a virtual hand for automated interaction testing.

## 2. Geometry and Blocker Inspection

### `GET /state/blockers`
Expose the current visibility geometry loaded from the SVG.
- **Response Schema:**
  ```json
  [
    {
      "id": "door_1",
      "type": "DOOR",
      "is_open": false,
      "points": [[x1, y1], [x2, y2]]
    }
  ]
  ```
- **Benefit:** Eliminates the need to manually parse SVG files to find door coordinates for testing.

## 3. Real-time Interaction Telemetry

### `GET /state/dwell`
Expose the internal state of the `DwellTracker`.
- **Fields:** `accumulated_time`, `is_triggered`, `last_point`, `target_id`.
- **Benefit:** Essential for diagnosing "deadlocks" where interactions aren't triggering despite valid input (e.g., the "dirty state" bug).

## 4. Diagnostics and Control

### `GET /state/logs`
Provide an endpoint to retrieve recent application logs or stream them via WebSocket.
- **Benefit:** Crucial for headless debugging on Raspberry Pi hardware where SSH access might be limited or stderr capture is cumbersome.

### `POST /config/viewport`
Allow directly setting the map's zoom, pan, and rotation.
- **Benefit:** Creates predictable "known-good" states for visual regression testing.

## 5. Metadata and Timing

### Logic Clock Sync
Ensure the API allows querying the current `time.monotonic()` value of the main process.
- **Benefit:** Helps remote clients avoid "immediate expiration" bugs caused by clock mismatches between the driver and the main loop.
