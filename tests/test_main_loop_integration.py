from light_map.core.main_loop import MainLoopController
from light_map.state.world_state import WorldState
from light_map.vision.infrastructure.process_manager import VisionProcessManager
from light_map.input.input_manager import InputManager
from light_map.core.common_types import DetectionResult, ResultType, Action
from unittest.mock import MagicMock


def test_main_loop_iteration():
    # Setup mocks
    state = WorldState()
    # Don't use spec for manager as it's complex and we dynamically add queues in __init__
    manager = MagicMock()
    manager.results_queue = MagicMock()
    manager.hand_queue = MagicMock()
    manager.aruco_queue = MagicMock()

    input_mgr = MagicMock(spec=InputManager)

    # Mock a result from queue
    res = DetectionResult(
        timestamp=1000, type=ResultType.GESTURE, data={"gesture": "PINCH"}
    )

    # Simulate first call returning a result, then empty
    manager.results_queue.empty.side_effect = [False, True]
    manager.results_queue.get_nowait.return_value = res

    manager.hand_queue.empty.return_value = True
    manager.aruco_queue.empty.return_value = True

    input_mgr.get_actions.return_value = [Action.SELECT]

    controller = MainLoopController(state, manager, input_mgr)

    # Run one tick
    controller.tick()

    # Verify state was updated
    assert state.gesture == "PINCH"
    assert state.hands_version > 0

    # Verify input was polled
    input_mgr.update_keyboard.assert_called_once()
    input_mgr.get_actions.assert_called_once()


def test_main_loop_frame_sync():
    state = WorldState()
    manager = MagicMock(spec=VisionProcessManager)
    input_mgr = MagicMock(spec=InputManager)

    _ = MainLoopController(state, manager, input_mgr)

    # Simulate a new frame from producer
    # (In real integration we'd use FrameProducer, here we mock the manager's access)
    pass
