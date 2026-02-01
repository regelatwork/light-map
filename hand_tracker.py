import sys
import os
import cv2
import time
import numpy as np
import mediapipe as mp

# Ensure we can import the local package
sys.path.insert(0, os.path.abspath("src"))

from light_map.camera import Camera
from light_map.gestures import detect_gesture, GestureType
from light_map.menu_config import ROOT_MENU
from light_map.input_manager import InputManager
from light_map.menu_system import MenuSystem
from light_map.renderer import Renderer

def main():
    # 1. Load Calibration
    calibration_file = 'projector_calibration.npz'
    if not os.path.exists(calibration_file):
        print(f"Error: {calibration_file} not found. Please run projector_calibration.py first.")
        return

    print(f"Loading calibration from {calibration_file}...")
    try:
        with np.load(calibration_file) as data:
            if 'projector_matrix' not in data:
                print("Error: Invalid calibration file (missing projector_matrix).")
                return
            transformation_matrix = data['projector_matrix']
            
            if 'resolution' in data:
                screen_w, screen_h = data['resolution']
            else:
                print("Warning: Legacy calibration detected. Using fallback resolution (1920x1080).")
                screen_w, screen_h = 1920, 1080
    except Exception as e:
        print(f"Error loading calibration: {e}")
        return

    print(f"Calibration loaded. Resolution: {screen_w}x{screen_h}")

    # 2. Setup Menu System
    menu = MenuSystem(screen_w, screen_h, ROOT_MENU)
    renderer = Renderer(screen_w, screen_h)
    input_manager = InputManager()

    # 2. Setup MediaPipe
    mp_hands = mp.solutions.hands
    hands = mp_hands.Hands(
        max_num_hands=2, 
        min_detection_confidence=0.7, 
        min_tracking_confidence=0.5
    )

    # 3. Setup Projector Window
    window_name = 'projection'
    cv2.namedWindow(window_name, cv2.WND_PROP_FULLSCREEN)
    cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    
    # Runtime Verification (Best Effort)
    try:
        # Note: getWindowImageRect can return (0,0) or include decorations on some OS/Window Managers
        rect = cv2.getWindowImageRect(window_name)
        if rect and rect[2] > 0 and rect[3] > 0:
            sys_w, sys_h = rect[2], rect[3]
            if (sys_w, sys_h) != (screen_w, screen_h):
                 print(f"Warning: Detected window size {sys_w}x{sys_h} does not match calibration {screen_w}x{screen_h}.")
                 # We continue with calibrated values as they are the source of truth for the matrix.
    except Exception:
        pass
    
    projection_screen = np.zeros((screen_h, screen_w, 3), dtype=np.uint8)

    # Variables for FPS calculation
    prev_time = 0

    # 4. Main Loop
    # Initialize camera once!
    try:
        with Camera() as cam:
            while True:
                frame = cam.read()
                if frame is None:
                    print("Failed to grab frame")
                    break

                # FPS Calculation
                curr_time = time.time()
                fps = 1 / (curr_time - prev_time) if prev_time != 0 else 0
                prev_time = curr_time

                # Flip and Convert
                # Note: We do NOT flip for processing to keep alignment with calibration,
                # unless we want to fix the "mirror" effect later.
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                results = hands.process(frame_rgb)

                projection_screen.fill(0)
                
                hand_count = 0
                gesture_text_y_offset = 400

                # 5. Menu & Gesture Logic
                
                # Default values for a frame with no hands
                cursor_x, cursor_y = -1, -1
                gesture = GestureType.NONE
                
                if results.multi_hand_landmarks and results.multi_handedness:
                    hand_count = len(results.multi_hand_landmarks)
                    
                    # For simplicity, we'll use the first detected hand as the primary controller
                    primary_hand_landmarks = results.multi_hand_landmarks[0]
                    primary_handedness = results.multi_handedness[0]
                    label = primary_handedness.classification[0].label

                    # Detect gesture for the primary hand
                    gesture = detect_gesture(primary_hand_landmarks.landmark, label)
                    
                    # Use index finger tip as the cursor
                    index_finger_tip = primary_hand_landmarks.landmark[mp_hands.HandLandmark.INDEX_FINGER_TIP]
                    cx = int(index_finger_tip.x * frame.shape[1])
                    cy = int(index_finger_tip.y * frame.shape[0])

                    # Transform to Projector Space to get the cursor position
                    camera_point = np.array([cx, cy], dtype=np.float32).reshape(1, 1, 2)
                    projector_point = cv2.perspectiveTransform(camera_point, transformation_matrix)
                    cursor_x, cursor_y = projector_point[0][0]
                
                # Update Input Manager
                # This helps smooth out the cursor and stabilize gestures
                input_manager.update(cursor_x, cursor_y, gesture, hand_count > 0)
                
                # Update Menu System
                if input_manager.is_hand_present():
                    menu_state = menu.update(input_manager.get_x(), input_manager.get_y(), input_manager.get_gesture())
                else:
                    # If no hand, we still need to update menu to handle timers (e.g., summon decay)
                    # We pass a neutral gesture and out-of-bounds coordinates
                    menu_state = menu.update(-1, -1, GestureType.NONE)

                # Render Menu
                menu_image = renderer.render(menu_state)
                
                # Combine layers
                # Add a transparent overlay to darken the background when menu is active
                if menu_state.is_visible:
                    overlay = np.zeros_like(projection_screen)
                    # overlay[:] = (70, 70, 70)
                    # cv2.addWeighted(projection_screen, 0.5, overlay, 0.5, 0, projection_screen)
                    # This is heavy, let's just add menu on top
                    pass

                # Add menu image to the projection screen
                # This assumes menu_image can have alpha, but it's 3-channel.
                # A simple mask can be used.
                mask = cv2.cvtColor(menu_image, cv2.COLOR_BGR2GRAY)
                _, mask = cv2.threshold(mask, 1, 255, cv2.THRESH_BINARY)
                mask_inv = cv2.bitwise_not(mask)
                
                img1_bg = cv2.bitwise_and(projection_screen, projection_screen, mask=mask_inv)
                img2_fg = cv2.bitwise_and(menu_image, menu_image, mask=mask)
                
                projection_screen = cv2.add(img1_bg, img2_fg)

                # Handle menu actions
                if menu_state.just_triggered_action:
                    print(f"Action triggered: {menu_state.just_triggered_action}")
                    # Here you would add logic to handle different actions,
                    # e.g., changing a setting, activating a mode, etc.

                # Display FPS and Hand Count
                cv2.putText(projection_screen, f"FPS: {int(fps)}", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 3, (0, 0, 255), 3)
                cv2.putText(projection_screen, f"Hands: {hand_count}", (50, 250), cv2.FONT_HERSHEY_SIMPLEX, 3, (0, 0, 255), 3)

                # For debugging, show cursor and gesture
                if input_manager.is_hand_present():
                    gesture_text = input_manager.get_gesture().name
                    dbg_x, dbg_y = input_manager.get_x(), input_manager.get_y()
                    cv2.putText(projection_screen, gesture_text, (dbg_x, dbg_y - 80), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 255), 3)
                    cv2.circle(projection_screen, (dbg_x, dbg_y), 15, (0, 255, 255), -1)

                cv2.imshow(window_name, projection_screen)

                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        hands.close()
        cv2.destroyAllWindows()

if __name__ == '__main__':
    main()
