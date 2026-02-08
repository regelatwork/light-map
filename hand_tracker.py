import sys
import os
import cv2
import time
import numpy as np
import mediapipe as mp
import argparse

# Ensure we can import the local package
sys.path.insert(0, os.path.abspath("src"))

from light_map.camera import Camera
from light_map.menu_config import ROOT_MENU
from light_map.common_types import MenuActions
from light_map.interactive_app import InteractiveApp, AppConfig

def main():
    parser = argparse.ArgumentParser(description="Hand Tracker & Menu System")
    parser.add_argument("--debug", action="store_true", help="Enable debug overlay", default=False)
    args = parser.parse_args()

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

    # 2. Setup App
    config = AppConfig(
        width=screen_w,
        height=screen_h,
        projector_matrix=transformation_matrix,
        root_menu=ROOT_MENU
    )
    app = InteractiveApp(config)
    app.set_debug_mode(args.debug)

    # 3. Setup MediaPipe
    mp_hands = mp.solutions.hands
    hands = mp_hands.Hands(
        max_num_hands=2, 
        min_detection_confidence=0.7, 
        min_tracking_confidence=0.5
    )

    # 4. Setup Projector Window
    window_name = 'projection'
    cv2.namedWindow(window_name, cv2.WND_PROP_FULLSCREEN)
    cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    
    # 5. Main Loop
    try:
        with Camera() as cam:
            while True:
                # A. Read Hardware
                frame = cam.read()
                if frame is None:
                    print("Failed to grab frame")
                    break

                # B. Process Hardware Input
                # Note: We do NOT flip for processing to keep alignment with calibration,
                # unless we want to fix the "mirror" effect later.
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = hands.process(frame_rgb)
                
                # C. Orchestrate Logic
                output_image, actions = app.process_frame(frame, results)

                # D. Update Hardware Output
                cv2.imshow(window_name, output_image)
                
                # E. Handle Actions
                for action in actions:
                    print(f"Executing Action: {action}")
                    if action == MenuActions.EXIT:
                        print("Exiting...")
                        return # Break loop
                    elif action == MenuActions.TOGGLE_DEBUG:
                        app.set_debug_mode(not app.debug_mode)

                # F. Handle Keyboard Interrupts
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
                elif key == ord('d'):
                    app.set_debug_mode(not app.debug_mode)
                    
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        hands.close()
        cv2.destroyAllWindows()

if __name__ == '__main__':
    main()
