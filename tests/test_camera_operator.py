import numpy as np
from light_map.vision.camera_operator import CameraOperator
import time


def test_camera_operator_shm_init():
    # Test initialization of shared memory
    width, height = 640, 480
    num_consumers = 2
    operator = CameraOperator(width=width, height=height, num_consumers=num_consumers)

    try:
        assert operator.shm is not None
        assert operator.shm_name is not None

        # Check buffer sizes: (N+2) frames + control block
        # Control block: ref_counts (N+2 ints), timestamps (N+2 longs), latest_id (1 int)
        # Assuming 4 bytes for int and 8 for long
        n = num_consumers + 2
        expected_control_size = (n * 4) + (n * 8) + 4
        frame_size = width * height * 3
        expected_total_size = expected_control_size + (n * frame_size)

        assert operator.shm.size >= expected_total_size
    finally:
        operator.cleanup()


def test_camera_operator_write_frame():
    width, height = 160, 120
    operator = CameraOperator(width=width, height=height, num_consumers=1)
    try:
        fake_frame = np.zeros((height, width, 3), dtype=np.uint8)
        fake_frame[10:20, 10:20] = [255, 0, 0]  # Blue square

        timestamp = int(time.time() * 1e6)
        buffer_id = operator._publish_frame(fake_frame, timestamp)

        assert buffer_id != -1
        # Check that we can read it back from SHM (manual check)
        n = 1 + 2
        # Control size: ref_counts (n*4) + timestamps (n*8) + shm_pushed (n*8) + latest_id (4)
        control_size = (n * 4) + (n * 8) + (n * 8) + 4
        frame_offset = control_size + (buffer_id * width * height * 3)
        shm_frame_buf = operator.shm.buf[
            frame_offset : frame_offset + width * height * 3
        ]
        shm_frame = np.frombuffer(shm_frame_buf, dtype=np.uint8).reshape(
            (height, width, 3)
        )
        assert np.array_equal(shm_frame, fake_frame)
        del shm_frame
        del shm_frame_buf
    finally:
        operator.cleanup()
