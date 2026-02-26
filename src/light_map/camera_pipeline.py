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
    landmarks: Any  # MediaPipe SolutionOutputs
    tokens: list  # List of Token objects
    fps: float


class CameraPipeline:
    def __init__(
        self,
        camera_instance,
        mp_hands,
        tracking_coordinator=None,
        app_config=None,
        map_system=None,
        map_config=None,
    ):
        """
        Initializes the camera processing pipeline.

        Args:
            camera_instance: An instance of light_map.camera.Camera
            mp_hands: Configured MediaPipe Hands instance.
            tracking_coordinator: Optional TrackingCoordinator for ArUco.
            app_config: Optional AppConfig for ArUco settings.
            map_system: Optional MapSystem for coordinate conversion.
            map_config: Optional MapConfigManager for token settings.
        """
        self.camera = camera_instance
        self.hands = mp_hands
        self.tracking_coordinator = tracking_coordinator
        self.app_config = app_config
        self.map_system = map_system
        self.map_config = map_config

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
            frame = self.camera.read()

            if frame is None:
                time.sleep(0.01)
                continue

            # CRITICAL: Copy frame immediately if the source reuses buffers.
            safe_frame = frame.copy()

            # 2. MediaPipe (Process Raw Frame)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.hands.process(frame_rgb)

            # 3. ArUco Background Tracking (if enabled)
            tokens = []
            if (
                self.tracking_coordinator
                and self.app_config
                and self.map_system
                and self.map_config
            ):
                # ArUco tracking updates map_system.ghost_tokens directly currently.
                self.tracking_coordinator.process_aruco_tracking(
                    safe_frame,
                    self.app_config,
                    self.map_system,
                    self.map_config,
                    camera_matrix=getattr(self.app_config, "camera_matrix", None),
                    dist_coeffs=getattr(self.app_config, "dist_coeffs", None),
                    rvec=getattr(self.app_config, "camera_rvec", None),
                    tvec=getattr(self.app_config, "camera_tvec", None),
                )
                tokens = list(self.map_system.ghost_tokens)

            # 4. FPS Calculation
            dt = time.time() - self._last_process_time
            current_fps = 1.0 / dt if dt > 0 else 0.0
            self._last_process_time = time.time()

            # 5. Update Shared State
            new_data = VisionData(
                frame_id=self._frame_id,
                frame=safe_frame,
                landmarks=results,
                tokens=tokens,
                fps=current_fps,
            )

            with self._lock:
                self._latest_data = new_data
                self._frame_id += 1
