import multiprocessing as mp
import logging
from typing import List, Optional
from light_map.vision.camera_operator import CameraOperator
from light_map.vision.workers import aruco_worker, hand_worker


class VisionProcessManager:
    """
    Supervisor class that manages the life cycle of all vision-related processes
    and the Shared Memory infrastructure.
    """

    def __init__(self, width: int = 1920, height: int = 1080, num_consumers: int = 2):
        self.width = width
        self.height = height
        self.num_consumers = num_consumers

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
        # ArUco Worker
        p_aruco = mp.Process(
            target=aruco_worker,
            args=(self.shm_name, self.results_queue, self.lock, self.stop_event),
            kwargs={
                "width": self.width,
                "height": self.height,
                "num_consumers": self.num_consumers,
            },
            name="ArucoWorker",
        )
        self.processes.append(p_aruco)

        # Hand Worker
        p_hand = mp.Process(
            target=hand_worker,
            args=(self.shm_name, self.results_queue, self.lock, self.stop_event),
            kwargs={
                "width": self.width,
                "height": self.height,
                "num_consumers": self.num_consumers,
            },
            name="HandWorker",
        )
        self.processes.append(p_hand)

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
