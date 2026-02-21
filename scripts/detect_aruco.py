import cv2
import sys
import os

# Add src to path so we can import light_map
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from light_map.camera import Camera

def detect_aruco():
    # ArUco dictionary to use (must match generator)
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    parameters = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)

    print("Initializing camera...")
    try:
        with Camera() as cam:
            print("Capturing frame...")
            # Capture a few frames to let auto-exposure settle
            for _ in range(15):
                frame = cam.read()
            
            if frame is None:
                print("Error: Could not read frame from camera.")
                return

            print("Detecting markers...")
            corners, ids, rejected = detector.detectMarkers(frame)

            if ids is not None:
                print(f"Detected {len(ids)} markers: {ids.flatten()}")
                # Draw detected markers
                cv2.aruco.drawDetectedMarkers(frame, corners, ids)
                
                # Draw labels with sizes if possible (optional, maybe too complex for now)
                for i in range(len(ids)):
                    c = corners[i][0]
                    # Calculate approximate side length in pixels
                    side_len = cv2.norm(c[0] - c[1])
                    cv2.putText(frame, f"ID: {ids[i][0]} Size: {side_len:.1f}px", 
                                (int(c[0][0]), int(c[0][1]) - 10), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            else:
                print("No markers detected.")

            output_file = "detected_markers.png"
            cv2.imwrite(output_file, frame)
            print(f"Saved result to {output_file}")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    detect_aruco()
