import multiprocessing as mp
import time
import logging
import cv2
import numpy as np
from typing import Optional, Tuple

from light_map.vision.frame_producer import FrameProducer
from light_map.vision.aruco_detector import ArucoTokenDetector
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
    projector_matrix: Optional[np.ndarray] = None,
    map_dims: Optional[Tuple[int, int]] = None,
    intrinsics_path: Optional[str] = None,
    extrinsics_path: Optional[str] = None,
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
    detector = ArucoTokenDetector(
        calibration_file=intrinsics_path,
        extrinsics_file=extrinsics_path,
        dictionary_type=aruco_dict_type
    )

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
                ts_shm_pulled = time.perf_counter_ns()
                frame_view = producer.get_latest_frame()
                if frame_view is None:
                    time.sleep(0.005)
                    continue

                ts_to_process = latest_ts
                ts_shm_pushed = producer.get_shm_pushed_timestamp()

                # OPTIMIZATION: If we have FOV parameters, crop inside the lease to copy less data
                crop_offset = None
                if projector_matrix is not None and map_dims is not None:
                    roi = detector.get_fov_roi(
                        frame_view.shape[:2], 1.0, projector_matrix, map_dims
                    )
                    if roi:
                        rx, ry, rw, rh = roi
                        # Copy only the ROI
                        frame_copy = frame_view[ry : ry + rh, rx : rx + rw].copy()
                        crop_offset = (rx, ry)
                    else:
                        frame_copy = frame_view.copy()
                else:
                    frame_copy = frame_view.copy()

            finally:
                # Release lease ASAP
                producer.release()
                frame_view = None

            # Perform detection outside the lease
            corners, ids = detector.detect_raw(
                frame_copy,
                projector_matrix=projector_matrix,
                map_dims=map_dims,
                crop_offset=crop_offset,
            )
            ts_work_done = time.perf_counter_ns()

            # Serialize results
            # corners are already a list of numpy arrays, convert to lists of lists
            data = {"corners": [c.tolist() for c in corners], "ids": ids}

            result = DetectionResult(
                timestamp=ts_to_process, type=ResultType.ARUCO, data=data
            )
            result.metadata["ts_shm_pushed"] = ts_shm_pushed
            result.metadata["ts_shm_pulled"] = ts_shm_pulled
            result.metadata["ts_work_done"] = ts_work_done

            try:
                # Push to queue without blocking
                result.metadata["ts_queue_pushed"] = time.perf_counter_ns()
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
    projector_matrix: Optional[np.ndarray] = None,
    map_dims: Optional[Tuple[int, int]] = None,
):
    """
    Worker function for hand detection. Consumes frames from shared memory,
    runs MediaPipe Hands, and pushes results to a queue.
    """
    import mediapipe as mp_lib
    from light_map.vision.aruco_detector import ArucoTokenDetector

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

    # Use Aruco detector helper for ROI calculation if needed
    aruco_detector = ArucoTokenDetector()

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
                ts_shm_pulled = time.perf_counter_ns()
                frame_view = producer.get_latest_frame()
                if frame_view is None:
                    time.sleep(0.005)
                    continue

                ts_to_process = latest_ts
                ts_shm_pushed = producer.get_shm_pushed_timestamp()

                # OPTIMIZATION: Crop inside the lease to copy less data
                crop_offset = None
                if projector_matrix is not None and map_dims is not None:
                    roi = aruco_detector.get_fov_roi(
                        frame_view.shape[:2], 1.0, projector_matrix, map_dims
                    )
                    if roi:
                        rx, ry, rw, rh = roi
                        # MediaPipe requires RGB images. cvtColor copies the data.
                        frame_rgb = cv2.cvtColor(
                            frame_view[ry : ry + rh, rx : rx + rw], cv2.COLOR_BGR2RGB
                        )
                        crop_offset = (rx, ry)
                    else:
                        frame_rgb = cv2.cvtColor(frame_view, cv2.COLOR_BGR2RGB)
                else:
                    frame_rgb = cv2.cvtColor(frame_view, cv2.COLOR_BGR2RGB)

            finally:
                # Release lease
                producer.release()
                frame_view = None

            # Process with MediaPipe outside the lease
            # MediaPipe process returns a NamedTuple which isn't picklable,
            # so we extract just what we need.
            results = hands.process(frame_rgb)
            ts_work_done = time.perf_counter_ns()

            landmarks_data = []
            handedness_data = []
            if results.multi_hand_landmarks:
                for i, hand_landmarks in enumerate(results.multi_hand_landmarks):
                    lm_list = []
                    for lm in hand_landmarks.landmark:
                        lx = lm.x
                        ly = lm.y
                        if crop_offset:
                            rx, ry = crop_offset
                            ch, cw = frame_rgb.shape[:2]
                            # Map to full frame pixels
                            px = lx * cw + rx
                            py = ly * ch + ry
                            # Map back to 0.0-1.0 relative to full frame
                            lx = px / width
                            ly = py / height

                        lm_list.append({"x": lx, "y": ly, "z": lm.z})

                    landmarks_data.append(lm_list)

                    # Handedness info
                    handedness = results.multi_handedness[i]
                    handedness_data.append(
                        {
                            "label": handedness.classification[0].label,
                            "score": handedness.classification[0].score,
                        }
                    )

            result = DetectionResult(
                timestamp=ts_to_process,
                type=ResultType.HANDS,
                data={"landmarks": landmarks_data, "handedness": handedness_data},
            )
            result.metadata["ts_shm_pushed"] = ts_shm_pushed
            result.metadata["ts_shm_pulled"] = ts_shm_pulled
            result.metadata["ts_work_done"] = ts_work_done

            try:
                result.metadata["ts_queue_pushed"] = time.perf_counter_ns()
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
