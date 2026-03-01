import multiprocessing as mp
import time
import logging
import cv2

from light_map.vision.frame_producer import FrameProducer
from light_map.common_types import DetectionResult, ResultType


def aruco_worker(
    shm_name: str,
    results_queue: mp.Queue,
    lock: mp.Lock,
    stop_event: mp.Event,
    width: int = 1920,
    height: int = 1080,
    num_consumers: int = 2,
    aruco_dict_type: int = cv2.aruco.DICT_4X4_50,
):
    """
    Worker function for ArUco detection. Consumes frames from shared memory,
    runs detection, and pushes results to a queue.
    """
    # 1. Initialize Producer
    producer = FrameProducer(
        shm_name=shm_name, width=width, height=height, num_consumers=num_consumers
    )
    producer.lock = lock

    # 2. Initialize Detector
    dictionary = cv2.aruco.getPredefinedDictionary(aruco_dict_type)
    parameters = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(dictionary, parameters)

    logging.info(f"ArUco Worker started (SHM: {shm_name})")
    last_processed_ts = -1

    try:
        while not stop_event.is_set():
            latest_ts = producer.get_latest_timestamp()

            # Frame dropping: if no new frame, wait
            if latest_ts is None or latest_ts <= last_processed_ts:
                time.sleep(0.005)
                continue

            try:
                # Acquire lease
                frame_view = producer.get_latest_frame()
                if frame_view is None:
                    time.sleep(0.005)
                    continue

                ts_to_process = latest_ts
                # Process: Convert to grayscale while holding lease
                # cvtColor copies the data, making it safe to process after release
                gray = cv2.cvtColor(frame_view, cv2.COLOR_BGR2GRAY)
            finally:
                # Release lease ASAP
                producer.release()

            # Perform detection outside the lease
            corners, ids, rejected = detector.detectMarkers(gray)

            # Serialize results
            data = {"corners": [], "ids": []}
            if ids is not None:
                # Convert numpy arrays to lists for Queue serialization
                data["corners"] = [c.tolist() for c in corners]
                data["ids"] = ids.flatten().tolist()

            result = DetectionResult(
                timestamp=ts_to_process, type=ResultType.ARUCO, data=data
            )

            try:
                # Push to queue without blocking
                results_queue.put_nowait(result)
            except mp.queues.Full:
                logging.warning("ArUco Worker: results_queue is full, dropping result.")

            last_processed_ts = ts_to_process

    except Exception as e:
        logging.error(f"ArUco Worker error: {e}", exc_info=True)
    finally:
        producer.close()
        logging.info("ArUco Worker stopped.")


def hand_worker(
    shm_name: str,
    results_queue: mp.Queue,
    lock: mp.Lock,
    stop_event: mp.Event,
    width: int = 1920,
    height: int = 1080,
    num_consumers: int = 2,
):
    """
    Worker function for hand detection. Consumes frames from shared memory,
    runs MediaPipe Hands, and pushes results to a queue.
    """
    import mediapipe as mp_lib

    # 1. Initialize Producer
    producer = FrameProducer(
        shm_name=shm_name, width=width, height=height, num_consumers=num_consumers
    )
    producer.lock = lock

    # 2. Initialize MediaPipe Hands
    mp_hands = mp_lib.solutions.hands
    hands = mp_hands.Hands(
        max_num_hands=2, min_detection_confidence=0.7, min_tracking_confidence=0.5
    )

    logging.info(f"Hand Worker started (SHM: {shm_name})")
    last_processed_ts = -1

    try:
        while not stop_event.is_set():
            latest_ts = producer.get_latest_timestamp()

            # Frame dropping
            if latest_ts is None or latest_ts <= last_processed_ts:
                time.sleep(0.005)
                continue

            try:
                # Acquire lease
                frame_view = producer.get_latest_frame()
                if frame_view is None:
                    time.sleep(0.005)
                    continue

                ts_to_process = latest_ts
                # MediaPipe requires RGB images. cvtColor copies the data.
                frame_rgb = cv2.cvtColor(frame_view, cv2.COLOR_BGR2RGB)
            finally:
                # Release lease
                producer.release()

            # Process with MediaPipe outside the lease
            # MediaPipe process returns a NamedTuple which isn't picklable,
            # so we extract just what we need.
            results = hands.process(frame_rgb)

            landmarks_data = []
            if results.multi_hand_landmarks:
                for hand_landmarks in results.multi_hand_landmarks:
                    lm_list = [
                        {"x": lm.x, "y": lm.y, "z": lm.z}
                        for lm in hand_landmarks.landmark
                    ]
                    landmarks_data.append(lm_list)

            result = DetectionResult(
                timestamp=ts_to_process,
                type=ResultType.HANDS,
                data={"landmarks": landmarks_data},
            )

            try:
                results_queue.put_nowait(result)
            except mp.queues.Full:
                logging.warning("Hand Worker: results_queue is full, dropping result.")

            last_processed_ts = ts_to_process

    except Exception as e:
        logging.error(f"Hand Worker error: {e}", exc_info=True)
    finally:
        hands.close()
        producer.close()
        logging.info("Hand Worker stopped.")
