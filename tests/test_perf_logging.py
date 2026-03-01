import time
import logging
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
    
    # Record some mock data
    controller.instrument.record_interval("test_metric", 10_000_000) # 10ms
    
    # Mock logging and time
    with patch("logging.info") as mock_log:
        # First tick should log because _last_report_time is 0
        controller.tick()
        assert mock_log.called
        
        # Reset and tick again immediately, should NOT log
        mock_log.reset_mock()
        controller.tick()
        assert not mock_log.called
        
        # Advance time by 5.1s
        with patch("time.perf_counter", return_value=time.perf_counter() + 6.0):
             controller.tick()
             assert mock_log.called
             # Check if p95_ms is in the log message
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
    
    # Manually populate instrument with mixed types as get_report() does
    controller.instrument.record_interval("test_metric", 10_000_000)
    
    with patch("logging.info") as mock_log:
        # Mock get_report to return mixed types
        with patch.object(controller.instrument, 'get_report', return_value={
            "test_metric": {"p95_ms": 10.0},
            "avg_total_latency_ms": 25.0 # This would cause TypeError before fix
        }):
            controller.tick()
            assert mock_log.called
            args, _ = mock_log.call_args
            assert "test_metric" in args[0]
            assert "10.0" in args[0]
            assert "avg_total_latency_ms" not in args[0] # Should be filtered out

def test_no_perf_logging_when_debug_inactive():
    state = WorldState()
    manager = MagicMock(spec=VisionProcessManager)
    manager.results_queue = MagicMock()
    manager.results_queue.empty.return_value = True
    input_mgr = MagicMock(spec=InputManager)
    
    controller = MainLoopController(state, manager, input_mgr)
    controller.debug_mode = False
    
    # Record some mock data
    controller.instrument.record_interval("test_metric", 10_000_000) # 10ms
    
    with patch("logging.info") as mock_log:
        controller.tick()
        # Filter out other logs if any (like "Menu action selected")
        perf_logs = [arg[0] for arg, _ in mock_log.call_args_list if "Performance Report" in str(arg)]
        assert len(perf_logs) == 0
