import sys
import os
import cv2
import time
import numpy as np
import mediapipe as mp

# Ensure we can import the local package
sys.path.insert(0, os.path.abspath("src"))

from light_map.camera import Camera
from light_map.gestures import detect_gesture
from projector_calibration import calibrate

def main():
    # 1. Calibrate Projector
    print("Starting calibration...")
    transformation_matrix = calibrate('camera_calibration.npz')
    
    if transformation_matrix is None:
        print("Calibration failed. Exiting.")
        return

    print("Projector calibrated. Starting hand tracking...")

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
    
    screen_w, screen_h = 1920, 1080
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

                if results.multi_hand_landmarks and results.multi_handedness:
                    hand_count = len(results.multi_hand_landmarks)
                    
                    for idx, (hand_landmarks, handedness) in enumerate(zip(results.multi_hand_landmarks, results.multi_handedness)):
                        label = handedness.classification[0].label # "Left" or "Right"
                        
                        # Detect Gesture
                        gesture = detect_gesture(hand_landmarks.landmark, label)
                        
                        # Calculate centroid (approximate) for text placement
                        # Or just stick it to the wrist
                        wrist = hand_landmarks.landmark[0]
                        cx_wrist = int(wrist.x * frame.shape[1])
                        cy_wrist = int(wrist.y * frame.shape[0])
                        
                        # Transform Wrist to Projector Space
                        camera_point = np.array([cx_wrist, cy_wrist], dtype=np.float32).reshape(1, 1, 2)
                        projector_point = cv2.perspectiveTransform(camera_point, transformation_matrix)
                        px_wrist, py_wrist = projector_point[0][0]

                        # Draw Gesture Name near the wrist on screen
                        cv2.putText(projection_screen, f"{label}: {gesture}", (int(px_wrist), int(py_wrist) - 50), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 0), 3)

                        # Draw Landmarks
                        for landmark in hand_landmarks.landmark:
                            # Normalized coordinates [0, 1]
                            # We need pixel coordinates in the CAMERA image
                            cx = int(landmark.x * frame.shape[1])
                            cy = int(landmark.y * frame.shape[0])

                            # Transform to Projector Space
                            camera_point = np.array([cx, cy], dtype=np.float32).reshape(1, 1, 2)
                            projector_point = cv2.perspectiveTransform(camera_point, transformation_matrix)
                            
                            px, py = projector_point[0][0]
                            
                            # Draw
                            cv2.circle(projection_screen, (int(px), int(py)), 3, (0, 50, 0), -1)

                # Display FPS and Hand Count
                cv2.putText(projection_screen, f"FPS: {int(fps)}", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 3, (0, 0, 255), 3)
                cv2.putText(projection_screen, f"Hands: {hand_count}", (50, 250), cv2.FONT_HERSHEY_SIMPLEX, 3, (0, 0, 255), 3)

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
