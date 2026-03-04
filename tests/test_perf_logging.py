import time
from unittest.mock import MagicMock, patch
from light_map.core.main_loop import MainLoopController
from light_map.core.world_state import WorldState
from light_map.vision.process_manager import VisionProcessManager
from light_map.input_manager import InputManager


def test_perf_logging_when_debug_active():
    # Setup
    state = WorldState()
    manager = MagicMock(spec=VisionProcessManager)
    manager.results_queue = MagicMock()
    manager.results_queue.empty.return_value = True
    input_mgr = MagicMock(spec=InputManager)

    controller = MainLoopController(state, manager, input_mgr)
    controller.debug_mode = True
    # Manually age the last report time to trigger logging immediately on first tick
    # MainLoopController uses its own _last_report_time
    controller._last_report_time = time.perf_counter() - 6.0

    # Record some mock data
    controller.instrument.record_interval("test_metric", 10_000_000)  # 10ms

    # Mock logging
    with patch("logging.debug") as mock_log:
        # First tick should log
        controller.tick()
        assert mock_log.called

        # Reset and tick again immediately, should NOT log
        mock_log.reset_mock()
        controller.tick()
        assert not mock_log.called

        # Advance time by manually aging again
        controller._last_report_time = time.perf_counter() - 6.0
        controller.tick()
        assert mock_log.called
        # Check if p95 is in the log message
        args, _ = mock_log.call_args
        assert "Performance Report" in args[0]
        assert "test_metric" in args[0]


def test_perf_logging_mixed_types():
    """Regression test for TypeError when report contains mixed types (dict and float)."""
    state = WorldState()
    manager = MagicMock(spec=VisionProcessManager)
    manager.results_queue = MagicMock()
    manager.results_queue.empty.return_value = True
    input_mgr = MagicMock(spec=InputManager)

    controller = MainLoopController(state, manager, input_mgr)
    controller.debug_mode = True
    # Manually age the last report time
    controller._last_report_time = time.perf_counter() - 6.0

    # Manually populate instrument with mixed types as get_report() does
    controller.instrument.record_interval("test_metric", 10_000_000)

    with patch("logging.debug") as mock_log:
        # Mock get_report to return mixed types
        with patch.object(
            controller.instrument,
            "get_report",
            return_value={
                "test_metric": {
                    "avg_ms": 10.0,
                    "p50_ms": 10.0,
                    "p90_ms": 10.0,
                    "p95_ms": 10.0,
                    "samples": 1,
                },
                "avg_total_latency_ms": 25.0,  # This would cause TypeError before fix
            },
        ):
            controller.tick()
            assert mock_log.called
            args, _ = mock_log.call_args
            assert "Performance Report" in args[0]
            assert "test_metric" in args[0]
            assert "10.0" in args[0]
            # It filters out things that are NOT dicts
            assert "avg_total_latency_ms" not in args[0]


def test_no_perf_logging_when_debug_inactive():
    state = WorldState()
    manager = MagicMock(spec=VisionProcessManager)
    manager.results_queue = MagicMock()
    manager.results_queue.empty.return_value = True
    input_mgr = MagicMock(spec=InputManager)

    controller = MainLoopController(state, manager, input_mgr)
    controller.debug_mode = False
    # Even with enough time passed, it shouldn't log if debug is inactive
    controller._last_report_time = time.perf_counter() - 6.0

    # Record some mock data
    controller.instrument.record_interval("test_metric", 10_000_000)  # 10ms

    with patch("logging.debug") as mock_log:
        controller.tick()
        # Filter out other logs if any
        perf_logs = [
            arg[0]
            for arg, _ in mock_log.call_args_list
            if "Performance Report" in str(arg)
        ]
        assert len(perf_logs) == 0
