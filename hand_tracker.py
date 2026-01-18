import sys
import os
import cv2
import numpy as np
import mediapipe as mp

# Ensure we can import the local package
sys.path.insert(0, os.path.abspath("src"))

from light_map.camera import Camera
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

    # 4. Main Loop
    # Initialize camera once!
    try:
        with Camera() as cam:
            while True:
                frame = cam.read()
                if frame is None:
                    print("Failed to grab frame")
                    break

                # Flip and Convert
                # Flip horizontally for selfie-view feeling? 
                # Note: This might affect the coordinate mapping if calibration wasn't flipped!
                # If we calibrated with the camera seeing the screen directly, 
                # flipping might invert the X axis relative to the calibration.
                # The original code flipped it. Let's assume the user wants the interaction to mirror them.
                # However, if we flip the image, the pixel coordinates change.
                # If we pass flipped image to MediaPipe, we get flipped coords.
                # If our calibration was done on unflipped images, we have a mismatch.
                # Ideally, we should NOT flip for processing, only for display (if we were displaying the camera feed).
                # But here we are projecting.
                
                # Let's stick to the original logic: "cv2.flip(frame, 1)"
                # But be aware: if calibration used raw frames, this flip invalidates the matrix unless accounted for.
                # Original code: 
                #   calibrate() -> uses raw capture
                #   loop -> capture() -> flip() -> process() -> transform()
                # THIS WAS A BUG in the original code (likely inverted X projection).
                # I will remove the flip for processing to ensure accuracy, 
                # or if flipping is desired for interaction, we must reflect the coords.
                
                # Let's process the RAW frame to match calibration space.
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                results = hands.process(frame_rgb)

                projection_screen.fill(0)

                if results.multi_hand_landmarks:
                    for hand_landmarks in results.multi_hand_landmarks:
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
                            cv2.circle(projection_screen, (int(px), int(py)), 10, (0, 255, 0), -1)

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