import time
from unittest.mock import MagicMock
from light_map.core.main_loop import MainLoopController
from light_map.core.world_state import WorldState
from light_map.common_types import DetectionResult, ResultType
from light_map.vision.frame_producer import FrameProducer


def test_telemetry_pipeline_integration():
    # Setup
    world_state = WorldState()
    manager = MagicMock()  # Removed spec
    manager.results_queue = MagicMock()
    input_manager = MagicMock()
    producer = MagicMock(spec=FrameProducer)

    # Configure producer mock
    ts_capture = 1000
    ts_shm_pushed = 1100
    producer.get_latest_timestamp.return_value = ts_capture
    producer.get_shm_pushed_timestamp.return_value = ts_shm_pushed
    producer.get_latest_frame.return_value = MagicMock()

    controller = MainLoopController(world_state, manager, input_manager, producer)

    # Configure manager's results queue for the FIRST tick (empty)
    manager.results_queue.empty.return_value = True

    # 1. Run one tick to simulate frame capture
    controller.tick()

    # Verify high-level capture intervals
    report = controller.instrument.get_report()
    assert "capture_to_shm" in report
    assert "shm_transit_to_main" in report

    # 2. Simulate a worker result arriving in the queue
    ts_shm_pulled = 1200
    ts_work_done = 1300
    ts_queue_pushed = 1400

    res = DetectionResult(
        timestamp=ts_capture,
        type=ResultType.ARUCO,
        data={"corners": [], "ids": []},
        metadata={
            "ts_shm_pushed": ts_shm_pushed,
            "ts_shm_pulled": ts_shm_pulled,
            "ts_work_done": ts_work_done,
            "ts_queue_pushed": ts_queue_pushed,
        },
    )

    # Mock manager's results queue for the SECOND tick
    manager.results_queue.empty.side_effect = [False, True]
    manager.results_queue.get_nowait.return_value = res

    # Run tick to drain queues
    controller.tick()

    # 3. Verify final report with all hops
    report = controller.instrument.get_report()

    # Interval checks
    assert (
        report["capture_to_shm"]["mean_ms"]
        == (ts_shm_pushed - ts_capture) / 1_000_000.0
    )
    assert (
        report["shm_transit_to_worker"]["mean_ms"]
        == (ts_shm_pulled - ts_shm_pushed) / 1_000_000.0
    )
    assert (
        report["worker_proc_time"]["mean_ms"]
        == (ts_work_done - ts_shm_pulled) / 1_000_000.0
    )
    assert (
        report["queue_wait_worker"]["mean_ms"]
        == (ts_queue_pushed - ts_work_done) / 1_000_000.0
    )
    assert "queue_transit_to_main" in report


def test_contention_tracking_integration():
    world_state = WorldState()
    manager = MagicMock()
    manager.results_queue = MagicMock()
    manager.results_queue.empty.return_value = True
    input_manager = MagicMock()
    producer = MagicMock(spec=FrameProducer)

    # Simulate some delay in get_latest_frame
    def delayed_frame():
        time.sleep(0.01)
        return MagicMock()

    producer.get_latest_timestamp.return_value = 2000
    producer.get_latest_frame.side_effect = delayed_frame

    controller = MainLoopController(world_state, manager, input_manager, producer)
    controller.tick()

    report = controller.instrument.get_report()
    assert "shm_wait_main" in report
    assert report["shm_wait_main"]["mean_ms"] >= 10.0
