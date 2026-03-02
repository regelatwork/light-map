# Performance Instrumentation

The system includes built-in performance monitoring to track pipeline latency and resource contention. This instrumentation is critical for identifying bottlenecks in the multi-process architecture.

## Pipeline "Hop" Tracking

To measure the end-to-end (glass-to-glass) latency of a frame, timestamps travel with the data through the pipeline:

- **Capture Process**: Records `ts_capture` (nanoseconds) when the camera frame is retrieved.
- **Shared Memory**: Records `ts_shm_pushed` when the frame is successfully written into the segment.
- **Worker Process**: Records `ts_shm_pulled`, `ts_work_done`, and `ts_queue_pushed` in the `metadata` field of the `DetectionResult`.
- **Main Process**: Records the final `ts_rendered` when the processed frame is displayed.

The `MainLoopController` aggregates these timestamps and passes them to the `LatencyInstrument` for analysis.

## Key Metrics

- **`capture_to_shm`**: Time taken by the camera driver and SHM write.
- **`shm_to_worker`**: IPC overhead for a worker to pick up the latest frame.
- **`worker_proc_time`**: Actual time spent by vision algorithms (Hand/ArUco detection).
- **`worker_to_main`**: IPC overhead for a result queue push and pull.
- **`main_render_time`**: Time taken to extract ROI, update state, and render the SVG map.
- **`total_latency`**: Total end-to-end glass-to-glass latency.

## Components

### `LatencyInstrument` (`src/light_map/core/analytics.py`)

A general-purpose telemetry aggregator that tracks intervals and calculates statistical percentiles (Mean, P50, P90, P95) over a sliding window (e.g., 100-500 samples).

### `track_wait` Context Manager

Used to measure time spent waiting on synchronization primitives:

```python
with track_wait("shm_lock_main", self.instrument):
    frame = producer.get_latest_frame()
```

## Reporting

Telemetry is periodically logged or can be accessed via `instrument.get_report()`. This data is used to optimize the system and ensure the user experience remains fluid (targeting \<100ms total latency).
