from light_map.core.analytics import LatencyInstrument


def test_latency_instrument_reporting():
    instrument = LatencyInstrument()

    # Simulate a frame lifecycle
    ts_capture = 1000000
    ts_detect = 1050000  # +50ms
    ts_render = 1100000  # +50ms

    instrument.record_capture(ts_capture)
    instrument.record_detection(ts_capture, ts_detect)
    instrument.record_render(ts_capture, ts_render)

    report = instrument.get_report()
    assert report["avg_total_latency_ms"] == 100.0
    assert report["avg_detection_lag_ms"] == 50.0
    assert report["avg_render_lag_ms"] == 50.0
