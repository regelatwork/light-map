import multiprocessing as mp
import logging
import numpy as np
from typing import List, Optional, Tuple, Dict, Any
from light_map.vision.camera_operator import CameraOperator
from light_map.vision.workers import aruco_worker, hand_worker
from light_map.vision.remote_driver import remote_driver_worker


class VisionProcessManager:
    """
    Supervisor class that manages the life cycle of all vision-related processes
    and the Shared Memory infrastructure.
    """

    def __init__(
        self,
        width: int = 1920,
        height: int = 1080,
        num_consumers: int = 2,
        projector_matrix: Optional[np.ndarray] = None,
        map_dims: Optional[Tuple[int, int]] = None,
        intrinsics_path: Optional[str] = None,
        extrinsics_path: Optional[str] = None,
        camera_matrix: Optional[np.ndarray] = None,
        distortion_coefficients: Optional[np.ndarray] = None,
        remote_mode_hands: str = "ignore",
        remote_mode_tokens: str = "ignore",
        remote_port: int = 8000,
        remote_origins: Optional[List[str]] = None,
        state_mirror: Optional[Dict[str, Any]] = None,
    ):
        self.width = width
        self.height = height
        self.num_consumers = num_consumers
        self.projector_matrix = projector_matrix
        self.map_dims = map_dims
        self.intrinsics_path = intrinsics_path
        self.extrinsics_path = extrinsics_path
        self.camera_matrix = camera_matrix
        self.distortion_coefficients = distortion_coefficients

        self.remote_mode_hands = remote_mode_hands
        self.remote_mode_tokens = remote_mode_tokens
        self.remote_port = remote_port
        self.remote_origins = remote_origins
        self.state_mirror = state_mirror

        self.operator: Optional[CameraOperator] = None
        self.shm_name: Optional[str] = None
        self.processes: List[mp.Process] = []

        # Shared Queues
        self.results_queue = mp.Queue()

        # Shared Sync Primitives
        self.stop_event = mp.Event()
        self.lock = mp.Lock()

    def start(self):
        """Initializes shared memory and spawns worker processes."""
        logging.info("Starting VisionProcessManager...")

        # Reset event
        self.stop_event.clear()

        # 1. Initialize CameraOperator (Producer)
        self.operator = CameraOperator(
            width=self.width, height=self.height, num_consumers=self.num_consumers
        )
        self.shm_name = self.operator.shm_name

        # Override operator's lock with our explicitly managed shared lock
        self.operator.lock = self.lock

        # 2. Spawn Child Processes

        # ArUco Worker (Physical)
        if self.remote_mode_tokens != "exclusive":
            aruco_worker_process = mp.Process(
                target=aruco_worker,
                args=(self.shm_name, self.results_queue, self.lock, self.stop_event),
                kwargs={
                    "width": self.width,
                    "height": self.height,
                    "num_consumers": self.num_consumers,
                    "projector_matrix": self.projector_matrix,
                    "map_dims": self.map_dims,
                    "intrinsics_path": self.intrinsics_path,
                    "extrinsics_path": self.extrinsics_path,
                    "camera_matrix": self.camera_matrix,
                    "distortion_coefficients": self.distortion_coefficients,
                },
                name="ArucoWorker",
            )
            self.processes.append(aruco_worker_process)

        # Hand Worker (Physical)
        if self.remote_mode_hands != "exclusive":
            hand_worker_process = mp.Process(
                target=hand_worker,
                args=(self.shm_name, self.results_queue, self.lock, self.stop_event),
                kwargs={
                    "width": self.width,
                    "height": self.height,
                    "num_consumers": self.num_consumers,
                    "projector_matrix": self.projector_matrix,
                    "map_dims": self.map_dims,
                },
                name="HandWorker",
            )
            self.processes.append(hand_worker_process)

        # Remote Driver Worker
        if self.remote_mode_hands != "ignore" or self.remote_mode_tokens != "ignore":
            remote_worker_process = mp.Process(
                target=remote_driver_worker,
                args=(
                    self.results_queue,
                    self.stop_event,
                    self.state_mirror,
                    self.shm_name,
                    self.lock,
                ),
                kwargs={
                    "port": self.remote_port,
                    "width": self.width,
                    "height": self.height,
                    "num_consumers": self.num_consumers,
                    "allowed_origins": self.remote_origins,
                },
                name="RemoteDriverWorker",
            )
            self.processes.append(remote_worker_process)

        for p in self.processes:
            p.daemon = True
            p.start()

        logging.info(f"Vision infrastructure ready with {len(self.processes)} workers.")

    def stop(self):
        """Gracefully stops all processes and unlinks shared memory."""
        logging.info("Stopping VisionProcessManager...")

        # Signal workers to stop
        self.stop_event.set()

        for p in self.processes:
            if p.is_alive():
                p.join(timeout=1.0)
                if p.is_alive():
                    logging.warning(
                        f"Process {p.name} did not terminate gracefully. Killing..."
                    )
                    p.kill()

        self.processes.clear()

        if self.operator:
            self.operator.cleanup()
            self.operator = None

        logging.info("VisionProcessManager stopped.")

    def is_healthy(self) -> bool:
        """Checks if all processes are still alive."""
        if not self.processes:
            return False
        return all(p.is_alive() for p in self.processes)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
