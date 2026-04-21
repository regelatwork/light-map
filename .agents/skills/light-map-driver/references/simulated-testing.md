# Simulated & Headless Testing

Use this guide for verifying logic without a physical table or for regression testing.

## Mock Token Injection
Use `POST /input/tokens` to place tokens at specific world coordinates.
**Rule:** Use coordinates that cross known map geometry (walls/low objects) to test tactical logic.

## Dwell Simulation
The `DwellTracker` requires a gesture (e.g., `Pointing`) to stay on a target for at least 2 seconds.
**Script Pattern:**
```python
for _ in range(10): # 5 seconds at 0.5s intervals
    httpx.post(f"{base_url}/input/hands/world", json=[{
        "world_x": wx, "world_y": wy, 
        "gesture": "Pointing",
        "unit_direction": {"x": 0, "y": 0, "z": 0} # No virtual offset
    }])
    time.sleep(0.5)
```

## Logic Verification
1. **Log Level:** Start the app with `--log-level DEBUG`.
2. **API Logs:** Fetch `GET /state/logs` and grep for `[ExclusiveVision]` or `[TacticalOverlay]`.
3. **State Check:** Query `GET /state/tactical_bonuses` to verify the calculated (AC, Reflex) tuples.
