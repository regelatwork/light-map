from light_map.vision.camera_operator import CameraOperator
from light_map.vision.frame_producer import FrameProducer


def test_reproduce_index_error():
    width, height = 100, 100
    num_consumers = 1

    # Producer
    operator = CameraOperator(width=width, height=height, num_consumers=num_consumers)
    shm_name = operator.shm_name
    lock = operator.lock

    # Consumer
    producer = FrameProducer(
        shm_name=shm_name, width=width, height=height, num_consumers=num_consumers
    )
    producer.lock = lock

    # Manually corrupt latest_id to something out of bounds
    print(f"Num buffers (n): {producer.n}")
    with lock:
        operator._latest_id[0] = 256

    print(f"Corrupted Latest ID: {producer._latest_id[0]}")

    # This should raise IndexError
    try:
        ts = producer.get_latest_timestamp()
        print(f"Latest TS: {ts}")
    except IndexError as e:
        print(f"Caught expected IndexError: {e}")

    # Clean up
    operator.cleanup()


if __name__ == "__main__":
    test_reproduce_index_error()
