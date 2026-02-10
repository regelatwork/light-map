import threading
import time
import cv2
import numpy as np
from dataclasses import dataclass
from typing import Optional, Any

from light_map.vision_enhancer import VisionEnhancer


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
        vision_enhancer: VisionEnhancer,
        mp_hands,  # MediaPipe Hands instance
    ):
        """
        Initializes the camera processing pipeline.
        
        Args:
            camera_instance: An instance of light_map.camera.Camera (or similar interface with .read())
            vision_enhancer: Configured VisionEnhancer instance.
            mp_hands: Configured MediaPipe Hands instance.
        """
        self.camera = camera_instance
        self.enhancer = vision_enhancer
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
        print("Camera Pipeline started.")

    def stop(self):
        """Stops the processing thread."""
        if self._thread is None:
            return
            
        print("Stopping Camera Pipeline...")
        self._stop_event.set()
        self._thread.join()
        self._thread = None
        print("Camera Pipeline stopped.")

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
            # OpenCV VideoCapture in Python returns a new array usually, but GStreamer might not?
            # Safer to copy if we are passing it to another thread while reading next.
            # However, np.array copy is expensive.
            # Let's assume our Camera class returns a unique buffer or we copy it.
            # Given we modify it in enhancer (maybe), let's copy to be safe if enhancer modifies in place.
            # VisionEnhancer.process returns a new image (cv2.cvtColor etc), so original 'frame' is safe?
            # Wait, enhancer.process(frame) calls:
            # gray = cv2.cvtColor(frame, ...)
            # clahe.apply(gray)
            # ...
            # It usually creates new arrays.
            
            # However, for the 'frame' stored in VisionData, we want the RAW frame or Enhanced?
            # Usually we display the raw or enhanced?
            # InteractiveApp uses 'frame' for 'process_frame' which passes it to 'calculate_ppi' 
            # and draws overlays on top of a black background usually (menu).
            # But wait, `process_frame` receives `frame` and uses it for `calculate_ppi`.
            # `InteractiveApp` returns `output_image` which is rendered by Renderer.
            # It doesn't seem to display the camera feed as background usually?
            # Ah, `cv2.imshow("projection", output_image)` shows the UI.
            # `cv2.imshow("AI Vision", debug)` shows camera.
            
            # So `VisionData.frame` is used for logic (PPI) and maybe debug display.
            
            # 2. Enhance
            # We need enhanced for MP.
            enhanced_bgr = self.enhancer.process(frame)
            frame_rgb = cv2.cvtColor(enhanced_bgr, cv2.COLOR_BGR2RGB)
            
            # 3. MediaPipe
            # Process strictly on this thread.
            results = self.hands.process(frame_rgb)
            
            # 4. FPS Calculation
            dt = time.time() - self._last_process_time
            current_fps = 1.0 / dt if dt > 0 else 0.0
            self._last_process_time = time.time()

            # 5. Update Shared State
            # We store the *original* frame (or enhanced? App uses frame for PPI).
            # App.process_frame(frame, results).
            # If we want to display enhanced in main thread for debug, we might want to store that too.
            # But VisionData def has one 'frame'. Let's store the raw frame as that's what App expects.
            # Wait, `hand_tracker.py` main loop does:
            # frame = cam.read()
            # enhanced = enhancer.process(frame)
            # ...
            # app.process_frame(frame, results)
            # So it passes raw frame.
            
            # We must ensure 'frame' is not modified by next read.
            # frame.copy() is safest.
            safe_frame = frame.copy()
            
            new_data = VisionData(
                frame_id=self._frame_id,
                frame=safe_frame,
                landmarks=results,
                fps=current_fps
            )
            
            with self._lock:
                self._latest_data = new_data
                self._frame_id += 1
            
            # Sleep specifically to yield? Or rely on IO blocking?
            # Camera.read() usually blocks until next frame (e.g. 30fps).
            # If it's non-blocking or very fast, we should limit loop rate to avoid 100% CPU.
            # But usually it's capped by HW.
