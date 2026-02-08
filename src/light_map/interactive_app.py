import cv2
import numpy as np
import time
from typing import Optional, List, Tuple, Any
from dataclasses import dataclass
import mediapipe as mp

from src.light_map.common_types import GestureType, MenuActions, MenuItem
from src.light_map.input_manager import InputManager
from src.light_map.menu_system import MenuSystem
from src.light_map.renderer import Renderer
from src.light_map.gestures import detect_gesture

@dataclass
class AppConfig:
    width: int
    height: int
    projector_matrix: np.ndarray
    root_menu: MenuItem

class InteractiveApp:
    def __init__(self, config: AppConfig, time_provider=time.monotonic):
        self.config = config
        self.time_provider = time_provider
        
        self.menu_system = MenuSystem(config.width, config.height, config.root_menu, time_provider=time_provider)
        self.renderer = Renderer(config.width, config.height)
        self.input_manager = InputManager()
        
        # State
        self.last_fps_time = 0.0
        self.fps = 0.0
        self.debug_mode = False

    def set_debug_mode(self, enabled: bool):
        self.debug_mode = enabled

    def reload_config(self, config: AppConfig):
        """Reloads the application configuration and re-initializes necessary components."""
        self.config = config
        # We also need to re-init menu system if screen size changed
        self.menu_system = MenuSystem(config.width, config.height, config.root_menu, time_provider=self.time_provider)
        self.renderer = Renderer(config.width, config.height)

    def process_frame(self, frame: np.ndarray, results: Any) -> Tuple[np.ndarray, List[str]]:
        """
        Process a single frame from the camera.
        
        Args:
            frame: The camera frame (BGR).
            results: MediaPipe Hands results.
            
        Returns:
            Tuple[output_image, triggered_actions]
        """
        current_time = self.time_provider()
        
        # 1. Update FPS
        if self.last_fps_time != 0:
            dt = current_time - self.last_fps_time
            if dt > 0:
                self.fps = 1.0 / dt
        self.last_fps_time = current_time

        # 2. Input Processing
        cursor_x, cursor_y = -1, -1
        gesture = GestureType.NONE
        is_hand_present = False
        hand_count = 0
        
        if results.multi_hand_landmarks and results.multi_handedness:
            hand_count = len(results.multi_hand_landmarks)
            primary_hand_landmarks = results.multi_hand_landmarks[0]
            primary_handedness = results.multi_handedness[0]
            label = primary_handedness.classification[0].label
            
            # Detect Gesture
            gesture = detect_gesture(primary_hand_landmarks.landmark, label)
            
            # Coordinate Transform
            # Index Finger Tip
            tip = primary_hand_landmarks.landmark[mp.solutions.hands.HandLandmark.INDEX_FINGER_TIP]
            cx = int(tip.x * frame.shape[1])
            cy = int(tip.y * frame.shape[0])
            
            # Camera -> Projector
            # Ensure matrix is float32 for perspectiveTransform
            matrix = self.config.projector_matrix.astype(np.float32)
            camera_point = np.array([cx, cy], dtype=np.float32).reshape(1, 1, 2)
            projector_point = cv2.perspectiveTransform(camera_point, matrix)
            cursor_x, cursor_y = int(projector_point[0][0][0]), int(projector_point[0][0][1])
            
            is_hand_present = True

        # 3. Update Input Manager
        self.input_manager.update(cursor_x, cursor_y, gesture, is_hand_present)
        
        # 4. Update Menu System
        smoothed_x = self.input_manager.get_x()
        smoothed_y = self.input_manager.get_y()
        smoothed_gesture = self.input_manager.get_gesture()
        
        menu_state = self.menu_system.update(smoothed_x, smoothed_y, smoothed_gesture)
        
        # 5. Render
        menu_image = self.renderer.render(menu_state)
        
        # 6. Compose
        # Start with black background (projector space)
        output = np.zeros((self.config.height, self.config.width, 3), dtype=np.uint8)
        
        # Add Menu
        # Assume menu_image is same size as output
        # Using simple add (assumes black background in menu_image where transparent)
        output = cv2.add(output, menu_image)
        
        # Debug Overlays
        if self.debug_mode:
            self._draw_debug_overlay(output, hand_count, smoothed_gesture, smoothed_x, smoothed_y)
        
        # 7. Actions
        actions = []
        if menu_state.just_triggered_action:
            actions.append(menu_state.just_triggered_action)
            
        return output, actions

    def _draw_debug_overlay(self, image, hand_count, gesture, x, y):
         cv2.putText(image, f"FPS: {int(self.fps)}", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
         cv2.putText(image, f"Hands: {hand_count}", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
         
         # Instructions
         cv2.putText(image, "Summon: Victory | Select: Fist", (50, self.config.height - 50), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (200, 200, 200), 2)
         
         if gesture != GestureType.NONE:
             # Ensure x, y are within bounds for drawing safely
             dx = max(0, min(x, self.config.width))
             dy = max(0, min(y, self.config.height))
             
             label = gesture.name if isinstance(gesture, GestureType) else str(gesture)
             cv2.putText(image, label, (dx, dy - 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
             cv2.circle(image, (dx, dy), 10, (0, 255, 255), -1)