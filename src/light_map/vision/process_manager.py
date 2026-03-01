import multiprocessing as mp
import logging
import signal
from typing import List, Optional
from light_map.vision.camera_operator import CameraOperator

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
        self.results_queue = mp.Queue()
        self.hand_queue = mp.Queue()
        self.aruco_queue = mp.Queue()

    def start(self):
        """Initializes shared memory and spawns worker processes."""
        logging.info("Starting VisionProcessManager...")
        
        # 1. Initialize CameraOperator (Producer)
        self.operator = CameraOperator(width=self.width, height=self.height, num_consumers=self.num_consumers)
        self.shm_name = self.operator.shm_name
        
        # 2. Spawn Child Processes (In Task 6/7)
        # self.processes.append(mp.Process(target=worker_loop, args=(...)))
        
        for p in self.processes:
            p.daemon = True
            p.start()
            
        logging.info(f"Vision infrastructure ready with {len(self.processes)} workers.")

    def stop(self):
        """Gracefully stops all processes and unlinks shared memory."""
        logging.info("Stopping VisionProcessManager...")
        
        for p in self.processes:
            if p.is_alive():
                p.terminate()
                p.join(timeout=1.0)
                if p.is_alive():
                    p.kill()
                    
        if self.operator:
            self.operator.cleanup()
            self.operator = None
            
        logging.info("VisionProcessManager stopped.")

    def is_healthy(self) -> bool:
        """Checks if all processes are still alive."""
        return all(p.is_alive() for p in self.processes)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
