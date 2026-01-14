import cv2
import numpy as np
import mediapipe as mp
from projector_calibration import calibrate
from camera import capture_image

def main():
    """
    Main function to run the hand tracking and projection.
    """
    # Calibrate the projector
    try:
        transformation_matrix = calibrate('camera_calibration.npz')
        print("Projector calibrated successfully.")
    except Exception as e:
        print(f"Error during calibration: {e}")
        return

    # Initialize MediaPipe Hands
    mp_hands = mp.solutions.hands
    hands = mp_hands.Hands(max_num_hands=2, min_detection_confidence=0.7, min_tracking_confidence=0.5)
    mp_drawing = mp.solutions.drawing_utils

    # Create a black fullscreen window to project the landmarks
    cv2.namedWindow('projection', cv2.WND_PROP_FULLSCREEN)
    cv2.setWindowProperty('projection', cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    projection_screen = np.zeros((1080, 1920, 3), dtype=np.uint8)

    while True:
        try:
            # Capture an image from the camera
            frame = capture_image()
        except Exception as e:
            print(f"Error capturing image: {e}")
            break

        # Flip the image horizontally for a later selfie-view display
        # and convert the BGR image to RGB.
        frame = cv2.cvtColor(cv2.flip(frame, 1), cv2.COLOR_BGR2RGB)

        # Process the image and find hands
        results = hands.process(frame)

        # Clear the projection screen
        projection_screen.fill(0)

        # Draw the hand annotations on the projection screen
        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                # Transform and draw landmarks
                for landmark in hand_landmarks.landmark:
                    # Get pixel coordinates from normalized coordinates
                    cx, cy = int(landmark.x * frame.shape[1]), int(landmark.y * frame.shape[0])

                    # Transform the point to projector coordinates
                    camera_point = np.array([cx, cy], dtype=np.float32).reshape(1, 1, 2)
                    projector_point = cv2.perspectiveTransform(camera_point, transformation_matrix)
                    px, py = projector_point[0][0]

                    # Draw the landmark on the projection screen
                    cv2.circle(projection_screen, (int(px), int(py)), 5, (0, 255, 0), -1)

        # Display the projection screen
        cv2.imshow('projection', projection_screen)

        # Break the loop if 'q' is pressed
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    hands.close()
    cv2.destroyAllWindows()

if __name__ == '__main__':
    main()
