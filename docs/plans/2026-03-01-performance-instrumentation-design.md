# Design: Performance Instrumentation and Contention Tracker

**Date:** 2026-03-01
**Status:** Validated
**Topic:** Performance Optimization & Analytics (bd-3af)

## Overview

This design implements high-level pipeline "hop" tracking and resource contention monitoring to identify bottlenecks in the Light Map multi-process architecture. It focuses on measuring the latency of frames as they transition between processes and the time spent waiting on synchronization primitives (locks/queues).

## Goals

- **Pipeline Visibility:** Track the end-to-end lifecycle of a frame across Capture, Worker, and Main processes.
- **Contention Detection:** Measure time spent waiting on Shared Memory locks and IPC queues.
- **Statistical Rigor:** Report Mean, P50, P90, and P95 percentiles for all tracked intervals.
- **Low Overhead:** Use nanosecond-precision timers (`perf_counter_ns`) and minimize new IPC synchronization.

## Architecture

### 1. Telemetry Engine (`LatencyInstrument`)

The existing `LatencyInstrument` will be refactored into a general-purpose telemetry aggregator:

- **Sample Buffers:** Uses `collections.deque` with a fixed window (e.g., 500 samples) for each tracked interval.
- **Percentile Calculation:** Calculates statistics (Mean, P50, P90, P95) from the sample buffers.
- **Dynamic Intervals:** Supports recording arbitrary intervals like `capture_to_shm`, `worker_proc_time`, and `main_render_time`.

### 2. Pipeline "Hop" Tracking

To track a frame's journey, timestamps will travel with the data:

- **`FrameMetadata` (SHM):** Includes `ts_capture` and `ts_shm_pushed`.
- **`DetectionResult` (common_types.py):** Adds a `metadata: Dict[str, int]` field to carry worker-side timestamps (`ts_shm_pulled`, `ts_work_done`, `ts_queue_pushed`) back to the Main Process.
- **Aggregation:** The `MainLoopController` closes the loop by passing these collected timestamps to the `LatencyInstrument`.

### 3. Contention Tracking

A new `track_wait` context manager in `analytics.py` will wrap blocking calls:

```python
with analytics.track_wait("shm_lock_main"):
    # Blocking operation
    frame = producer.get_latest_frame()
```

The duration spent inside the context will be recorded as a "wait time" metric.

## Implementation Details

### Data Structures

- **`LatencyInstrument`**:
  - `history: Dict[str, deque[int]]` - Stores nanosecond intervals.
  - `record_interval(name: str, duration_ns: int)` - Adds a sample.
  - `get_report() -> Dict[str, Dict[str, float]]` - Returns percentiles for all intervals.

### Components Impacted

- **`src/light_map/core/analytics.py`**: Core logic for `LatencyInstrument` and `track_wait`.
- **`src/light_map/common_types.py`**: Extension of `DetectionResult` to carry metadata.
- **`src/light_map/core/main_loop.py`**: Integration for aggregating timestamps and recording render intervals.
- **`src/light_map/vision/process_manager.py`**: Integration for worker-side timestamping.
- **`src/light_map/vision/frame_producer.py`**: Integration for capture-side timestamping.

## Testing & Validation

- **Unit Tests (`tests/test_latency_instrument.py`)**: Verify percentile calculations against known distributions.
- **Mocked Pipeline Test**: Simulate a full frame lifecycle (Capture -> SHM -> Worker -> Main) and verify interval calculations.
- **Contention Simulation**: Mock a slow lock and verify that `track_wait` accurately captures the delay.

## Success Criteria

- [ ] Percentiles (P50/P90/P95) are visible in logs or reports.
- [ ] "Hop" latency between Capture and Main is accurately measured.
- [ ] Lock contention in the Main Process is quantified in milliseconds.
- [ ] Telemetry overhead is negligible (\<0.1ms per frame).
