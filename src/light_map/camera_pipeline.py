import threading
import time
import cv2
import numpy as np
import logging
from dataclasses import dataclass
from typing import Optional, Any


@dataclass(frozen=True)
class VisionData:
    frame_id: int
    frame: np.ndarray  # BGR uint8
    landmarks: Any  # MediaPipe SolutionOutputs (multi_hand_landmarks object)
    fps: float


class CameraPipeline:
    def __init__(
        self,
        camera_instance,  # Expects an already open camera object (from light_map.camera)
        mp_hands,  # MediaPipe Hands instance
    ):
        """
        Initializes the camera processing pipeline.

        Args:
            camera_instance: An instance of light_map.camera.Camera (or similar interface with .read())
            mp_hands: Configured MediaPipe Hands instance.
        """
        self.camera = camera_instance
        self.hands = mp_hands

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Shared State
        self._latest_data: Optional[VisionData] = None
        self._frame_id = 0
        self._last_process_time = 0.0

    def start(self):
        """Starts the processing thread."""
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logging.info("Camera Pipeline started.")

    def stop(self):
        """Stops the processing thread."""
        if self._thread is None:
            return

        logging.info("Stopping Camera Pipeline...")
        self._stop_event.set()
        self._thread.join()
        self._thread = None
        logging.info("Camera Pipeline stopped.")

    def get_latest(self) -> Optional[VisionData]:
        """Returns the latest processed frame data in a thread-safe manner."""
        with self._lock:
            return self._latest_data

    def _run(self):
        """Main loop for the processing thread."""
        while not self._stop_event.is_set():
            # 1. Capture
            # Note: camera.read() might block, but usually returns quickly if frame ready.
            # Using our custom Camera class, read() handles GStreamer/OpenCV.
            frame = self.camera.read()

            if frame is None:
                # If camera fails, maybe retry or just continue?
                # For now, just skip loop to avoid crashing
                time.sleep(0.01)
                continue

            # CRITICAL: Copy frame immediately if the source reuses buffers.
            safe_frame = frame.copy()

            # 2. MediaPipe (Process Raw Frame)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Process strictly on this thread.
            results = self.hands.process(frame_rgb)

            # 3. FPS Calculation
            dt = time.time() - self._last_process_time
            current_fps = 1.0 / dt if dt > 0 else 0.0
            self._last_process_time = time.time()

            # 4. Update Shared State
            new_data = VisionData(
                frame_id=self._frame_id,
                frame=safe_frame,
                landmarks=results,
                fps=current_fps,
            )

            with self._lock:
                self._latest_data = new_data
                self._frame_id += 1

            # Sleep specifically to yield? Or rely on IO blocking?
            # Camera.read() usually blocks until next frame (e.g. 30fps).
            # If it's non-blocking or very fast, we should limit loop rate to avoid 100% CPU.
            # But usually it's capped by HW.
