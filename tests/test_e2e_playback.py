import numpy as np
import time
import cv2
import threading
from light_map.vision.infrastructure.process_manager import VisionProcessManager
from light_map.core.main_loop import MainLoopController
from light_map.state.world_state import WorldState
from light_map.input.input_manager import InputManager
from light_map.vision.infrastructure.frame_producer import FrameProducer


def test_multiprocessing_e2e():
    """
    Simulate E2E video playback to verify SHM, Worker processes, and MainLoopController.
    """
    manager = VisionProcessManager(width=320, height=240, num_consumers=2)
    manager.start()

    state = WorldState()
    input_manager = InputManager()
    producer = FrameProducer(shm_name=manager.shm_name, width=320, height=240)
    producer.lock = manager.lock

    main_loop = MainLoopController(state, manager, input_manager, producer)

    # Create fake camera
    stop_event = threading.Event()

    def mock_camera_loop():
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        cv2.rectangle(frame, (100, 100), (200, 200), (255, 255, 255), -1)

        while not stop_event.is_set():
            manager.operator._publish_frame(frame, time.time_ns())
            time.sleep(0.033)

    cam_thread = threading.Thread(target=mock_camera_loop)
    cam_thread.start()

    render_count = 0

    def mock_render(state, actions):
        nonlocal render_count
        render_count += 1
        return True

    try:
        # Run main loop manually for a few iterations
        start_time = time.time()
        while time.time() - start_time < 1.0:  # Run for 1 second
            actions = main_loop.tick()
            mock_render(state, actions)

        assert render_count > 0, "Render callback was never triggered"
        assert manager.is_healthy(), "Workers crashed during playback"
    finally:
        stop_event.set()
        cam_thread.join()
        main_loop.stop()
