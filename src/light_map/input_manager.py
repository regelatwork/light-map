import time
from typing import Optional, Tuple, Any
import numpy as np
import cv2
from src.light_map.common_types import GestureType
from src.light_map.gestures import detect_gesture

class InputManager:
    def __init__(self, flicker_timeout: float = 0.5):
        self.flicker_timeout = flicker_timeout
        self.primary_hand_label: Optional[str] = None
        self.last_seen_time: float = 0.0
        # State to track if we are currently "holding" a lost hand
        self.is_tracking_lost_hand: bool = False

    def process(self, results: Any, timestamp: float, frame_shape: Tuple[int, int, int], transformation_matrix: Optional[np.ndarray] = None) -> Optional[Tuple[int, int, GestureType]]:
        """
        Process MediaPipe results and return a stable (x, y, gesture) tuple in Projector Space.
        
        Args:
            results: MediaPipe Hands results object.
            timestamp: Current timestamp (seconds).
            frame_shape: (height, width, channels) of the camera frame.
            transformation_matrix: Homography matrix for projector calibration. 
                                   If None, returns camera pixel coordinates.
        
        Returns:
            (x, y, gesture) or None if no valid input.
        """
        
        # 1. Extract candidates
        candidates = []
        if results.multi_hand_landmarks and results.multi_handedness:
            for idx, (hand_landmarks, handedness) in enumerate(zip(results.multi_hand_landmarks, results.multi_handedness)):
                label = handedness.classification[0].label # "Left" or "Right"
                
                # Detect Gesture
                gesture_str = detect_gesture(hand_landmarks.landmark, label)
                
                # Map string to Enum
                try:
                    gesture_enum = GestureType(gesture_str)
                except ValueError:
                    gesture_enum = GestureType.UNKNOWN

                # Get coordinates (Wrist)
                wrist = hand_landmarks.landmark[0]
                cx = int(wrist.x * frame_shape[1])
                cy = int(wrist.y * frame_shape[0])
                
                # Transform to Projector Space if matrix provided
                if transformation_matrix is not None:
                    camera_point = np.array([cx, cy], dtype=np.float32).reshape(1, 1, 2)
                    projector_point = cv2.perspectiveTransform(camera_point, transformation_matrix)
                    px, py = projector_point[0][0]
                    coords = (int(px), int(py))
                else:
                    coords = (cx, cy)
                
                candidates.append({
                    "label": label,
                    "coords": coords,
                    "gesture": gesture_enum
                })

        # 2. Sticky Hand Logic
        selected_hand = None
        
        if not candidates:
            # No hands detected
            if self.primary_hand_label and (timestamp - self.last_seen_time < self.flicker_timeout):
                # Flicker Recovery: Don't drop yet, but we have no new data.
                # Return None, but keep state.
                return None
            else:
                # Timeout expired or no history
                self.primary_hand_label = None
                return None
        
        # We have candidates
        if self.primary_hand_label:
            # Try to find the primary hand
            for cand in candidates:
                if cand["label"] == self.primary_hand_label:
                    selected_hand = cand
                    break
            
            if not selected_hand:
                # Primary hand not found in candidates (maybe switched hands?)
                # Check timeout
                if timestamp - self.last_seen_time < self.flicker_timeout:
                    # Treat as flicker, return None, keep expecting it
                    return None
                else:
                    # Timeout -> Switch to new hand (first available)
                    selected_hand = candidates[0]
                    self.primary_hand_label = selected_hand["label"]
        else:
            # No primary hand, pick the first one
            selected_hand = candidates[0]
            self.primary_hand_label = selected_hand["label"]

        # 3. Update State
        self.last_seen_time = timestamp
        
        return (selected_hand["coords"][0], selected_hand["coords"][1], selected_hand["gesture"])

