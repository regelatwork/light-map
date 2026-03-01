import cv2
import time
import logging
from typing import Optional, List
from light_map.core.world_state import WorldState
from light_map.vision.process_manager import VisionProcessManager
from light_map.vision.frame_producer import FrameProducer
from light_map.input_manager import InputManager
from light_map.common_types import DetectionResult, Action

class MainLoopController:
    """
    Heart of the MainProcess. Aggregates results, updates state,
    and coordinates rendering.
    """
    def __init__(
        self, 
        world_state: WorldState, 
        process_manager: VisionProcessManager, 
        input_manager: InputManager,
        frame_producer: Optional[FrameProducer] = None,
        target_fps: int = 60
    ):
        self.state = world_state
        self.manager = process_manager
        self.input = input_manager
        self.producer = frame_producer
        self.target_fps = target_fps
        self.frame_time = 1.0 / target_fps
        
        self.is_running = False

    def tick(self) -> List[Action]:
        """Performs one iteration of the main loop."""
        # 1. Update Background from SHM
        if self.producer:
            # Check for new frame
            ts = self.producer.get_latest_timestamp()
            if ts is not None and ts > self.state.last_frame_timestamp:
                shm_view = self.producer.get_latest_frame()
                if shm_view is not None:
                    self.state.update_from_frame(shm_view, ts)
                    self.producer.release()
                    
        # 2. Drain Vision Results from Queues
        self._drain_queues()
        
        # 3. Poll Hardware Input
        key = cv2.waitKey(1)
        self.input.update_keyboard(key)
        
        # 4. Get Semantic Actions
        actions = self.input.get_actions()
        
        return actions

    def _drain_queues(self):
        """Pulls all pending results from detector queues and applies them to WorldState."""
        # Check combined results queue
        while not self.manager.results_queue.empty():
            try:
                res = self.manager.results_queue.get_nowait()
                if isinstance(res, DetectionResult):
                    self.state.apply(res)
            except Exception:
                break
                
        # Also check specialized queues if used
        while not self.manager.hand_queue.empty():
            try:
                res = self.manager.hand_queue.get_nowait()
                self.state.apply(res)
            except Exception:
                break
                
        while not self.manager.aruco_queue.empty():
            try:
                res = self.manager.aruco_queue.get_nowait()
                self.state.apply(res)
            except Exception:
                break

    def run(self, render_callback):
        """Starts the high-frequency polling loop."""
        self.is_running = True
        logging.info("Main loop started.")
        
        try:
            while self.is_running:
                start_time = time.perf_counter()
                
                # 1. Process State
                actions = self.tick()
                
                # 2. Trigger Render if needed
                if self.state.is_dirty or actions:
                    render_callback(self.state, actions)
                    self.state.clear_dirty()
                    
                # 3. Handle Frame Rate
                elapsed = time.perf_counter() - start_time
                wait_time = max(0.001, self.frame_time - elapsed)
                time.sleep(wait_time)
                
        except KeyboardInterrupt:
            logging.info("Interrupted by user.")
        finally:
            self.stop()

    def stop(self):
        self.is_running = False
        logging.info("Main loop stopping...")
        if self.producer:
            self.producer.close()
        self.manager.stop()
