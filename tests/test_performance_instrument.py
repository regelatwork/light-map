import time

import pytest

from light_map.core.analytics import LatencyInstrument, track_wait


def test_latency_instrument_percentiles():
    instrument = LatencyInstrument(window_size=100)

    # Record 100 samples from 1 to 100 ms
    for i in range(1, 101):
        instrument.record_interval("test_interval", i * 1_000_000)  # ms to ns

    report = instrument.get_report()
    stats = report["test_interval"]

    assert stats["avg_ms"] == pytest.approx(50.5, abs=0.1)
    assert stats["p50_ms"] == pytest.approx(50.5, abs=1.0)
    assert stats["p90_ms"] == pytest.approx(90.5, abs=1.0)
    assert stats["p95_ms"] == pytest.approx(95.5, abs=1.0)


def test_track_wait_context_manager():
    instrument = LatencyInstrument()

    with track_wait("test_lock", instrument):
        time.sleep(0.05)  # 50ms

    report = instrument.get_report()
    assert "test_lock" in report
    assert report["test_lock"]["avg_ms"] >= 50.0


def test_latency_instrument_empty():
    instrument = LatencyInstrument()
    report = instrument.get_report()
    assert report == {}


def test_backward_compatibility():
    # Ensure old methods still work but might report differently if we changed internal units
    instrument = LatencyInstrument()

    ts_capture = time.perf_counter_ns()
    instrument.record_capture(ts_capture)

    # Simulate some delay
    time.sleep(0.01)
    ts_detect = time.perf_counter_ns()
    instrument.record_detection(ts_capture, ts_detect)

    time.sleep(0.01)
    ts_render = time.perf_counter_ns()
    instrument.record_render(ts_capture, ts_render)

    report = instrument.get_report()
    # We expect intervals like "capture_to_detect", "detect_to_render", "total_latency"
    assert "total_latency" in report
    assert report["total_latency"]["avg_ms"] >= 20.0
