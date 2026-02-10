import sys
import os
import cv2
import numpy as np
import mediapipe as mp
import argparse
import time

# Ensure we can import the local package
sys.path.insert(0, os.path.abspath("src"))

from light_map.camera import Camera
from light_map.menu_config import ROOT_MENU
from light_map.common_types import MenuActions
from light_map.interactive_app import InteractiveApp, AppConfig
from light_map.calibration_logic import run_calibration_sequence
from light_map.vision_enhancer import VisionEnhancer
from light_map.camera_pipeline import CameraPipeline


def main():
    parser = argparse.ArgumentParser(description="Hand Tracker & Menu System")
    parser.add_argument(
        "--debug", action="store_true", help="Enable debug overlay", default=False
    )
    parser.add_argument(
        "--map", type=str, help="Path to SVG map file to load", default=None
    )
    parser.add_argument(
        "--view-enhanced",
        action="store_true",
        help="View the enhanced AI vision frame",
        default=False,
    )
    args = parser.parse_args()

    # 1. Load Calibration
    calibration_file = "projector_calibration.npz"

    # Helper to load calibration
    def load_calib():
        if not os.path.exists(calibration_file):
            print(f"Warning: {calibration_file} not found. Using default resolution.")
            return None, 1920, 1080
        try:
            with np.load(calibration_file) as data:
                if "projector_matrix" not in data:
                    print("Error: Invalid calibration file (missing projector_matrix).")
                    return None, 1920, 1080
                matrix = data["projector_matrix"]
                if "resolution" in data:
                    w, h = data["resolution"]
                else:
                    w, h = 1920, 1080
                return matrix, w, h
        except Exception as e:
            print(f"Error loading calibration: {e}")
            return None, 1920, 1080

    transformation_matrix, screen_w, screen_h = load_calib()

    if transformation_matrix is None:
        print("Starting uncalibrated (or using defaults). Please calibrate via menu.")
        # Create a dummy identity matrix if calibration missing, so app doesn't crash
        transformation_matrix = np.eye(3, dtype=np.float32)

    print(f"Calibration loaded. Resolution: {screen_w}x{screen_h}")

    # 2. Setup App
    config = AppConfig(
        width=screen_w,
        height=screen_h,
        projector_matrix=transformation_matrix,
        root_menu=ROOT_MENU,
    )
    app = InteractiveApp(config)
    app.set_debug_mode(args.debug)

    if args.map:
        if os.path.exists(args.map):
            print(f"Loading map: {args.map}")
            app.load_map(args.map)
        else:
            print(f"Error: Map file not found: {args.map}")

    # 3. Setup Vision Enhancer & MediaPipe
    # Load vision params from config
    saved_gamma, saved_clahe = app.map_config.get_vision_params()
    enhancer = VisionEnhancer(gamma=saved_gamma, clahe_clip=saved_clahe)

    mp_hands = mp.solutions.hands
    hands = mp_hands.Hands(
        max_num_hands=2, min_detection_confidence=0.7, min_tracking_confidence=0.5
    )

    # 4. Setup Projector Window
    window_name = "projection"
    cv2.namedWindow(window_name, cv2.WND_PROP_FULLSCREEN)
    cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    if args.view_enhanced:
        cv2.namedWindow("AI Vision (Enhanced)", cv2.WINDOW_NORMAL)

    # 5. Main Loop
    last_processed_id = -1
    pipeline = None
    
    try:
        with Camera() as cam:
            # Initialize Pipeline
            pipeline = CameraPipeline(cam, enhancer, hands)
            pipeline.start()
            
            try:
                while True:
                    # A. Get Latest Data
                    data = pipeline.get_latest()
                    
                    if data is None:
                        # Waiting for first frame
                        time.sleep(0.01)
                        continue

                    # B. Check if new
                    if data.frame_id > last_processed_id:
                        last_processed_id = data.frame_id
                        
                        # Update Debug View if requested
                        if args.view_enhanced:
                            # We need to re-enhance or store enhanced frame in data?
                            # Currently pipeline stores raw frame.
                            # If we want to show enhanced, we should re-run enhance or store it.
                            # Re-running is wasteful. 
                            # Ideally pipeline stores enhanced frame too?
                            # For now, just re-enhance for debug view (it's fast enough on CPU usually, or skip it)
                            debug_img = enhancer.process(data.frame)
                            
                            cv2.putText(
                                debug_img,
                                f"Gamma: {enhancer.gamma:.1f} ([/])",
                                (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.7,
                                (0, 255, 0),
                                2,
                            )
                            cv2.putText(
                                debug_img,
                                f"CLAHE: {enhancer.clahe.getClipLimit():.1f} ({{/}})",
                                (10, 60),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.7,
                                (0, 255, 0),
                                2,
                            )
                            cv2.putText(
                                debug_img,
                                f"Pipe FPS: {data.fps:.1f}",
                                (10, 90),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.7,
                                (0, 255, 0),
                                2,
                            )

                            # Resize for display if too large
                            h, w = debug_img.shape[:2]
                            target_h = 480
                            if h > target_h:
                                scale = target_h / h
                                new_w = int(w * scale)
                                debug_img = cv2.resize(debug_img, (new_w, target_h))

                            cv2.imshow("AI Vision (Enhanced)", debug_img)

                        # C. Orchestrate Logic
                        # app.process_frame returns the UI image
                        output_image, actions = app.process_frame(data.frame, data.landmarks)

                        # D. Update Hardware Output
                        cv2.imshow(window_name, output_image)
                        
                        # Process Actions
                        should_break = False
                        for action in actions:
                            print(f"Executing Action: {action}")
                            if action == MenuActions.EXIT:
                                print("Exiting...")
                                should_break = True
                            elif action == MenuActions.CALIBRATE:
                                print("Starting Calibration...")
                                # STOP Pipeline to free camera
                                pipeline.stop()
                                
                                new_matrix = run_calibration_sequence(
                                    cam, width=screen_w, height=screen_h
                                )

                                if new_matrix is not None:
                                    print("Calibration successful! Saving...")
                                    np.savez(
                                        calibration_file,
                                        projector_matrix=new_matrix,
                                        resolution=np.array([screen_w, screen_h]),
                                    )
                                    print("Reloading application configuration...")
                                    new_config = AppConfig(
                                        width=screen_w,
                                        height=screen_h,
                                        projector_matrix=new_matrix,
                                        root_menu=ROOT_MENU,
                                    )
                                    app.reload_config(new_config)
                                else:
                                    print("Calibration failed or cancelled.")

                                # Restore Window
                                cv2.namedWindow(window_name, cv2.WND_PROP_FULLSCREEN)
                                cv2.setWindowProperty(
                                    window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN
                                )
                                
                                # RESTART Pipeline
                                pipeline.start()

                            elif action == MenuActions.TOGGLE_DEBUG:
                                app.set_debug_mode(not app.debug_mode)

                        if should_break:
                            break
                    
                    else:
                        # No new data: Just handle UI events (keyboard) and sleep
                        # If we wanted high FPS UI independent of Camera, we would call app.render() here
                        # But app.process_frame does logic AND render.
                        # We could split them, but for now, just waiting is fine.
                        time.sleep(0.001)

                    # F. Handle Keyboard Interrupts (Check every loop iteration)
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord("q"):
                        break
                    elif key == ord("d"):
                        app.set_debug_mode(not app.debug_mode)

                    # Tuning Controls - Direct modification of shared enhancer object?
                    # Enhancer is used in thread. Is it thread safe?
                    # VisionEnhancer properties (gamma, clahe) are Python objects.
                    # Writing primitive (float) is atomic-ish.
                    # Recreating CLAHE object might race.
                    # Ideally we should use a lock or queue for params update.
                    # But for dev debug, it's probably okay or we can pause pipeline.
                    
                    # Let's be safe: Stop pipeline, update, start? Too slow.
                    # Or just accept race condition for debug tool.
                    elif key == ord("["):
                        enhancer.set_gamma(enhancer.gamma - 0.1)
                        app.map_config.set_vision_params(enhancer.gamma, enhancer.clahe_clip)
                        print(f"Gamma: {enhancer.gamma:.1f}")
                    elif key == ord("]"):
                        enhancer.set_gamma(enhancer.gamma + 0.1)
                        app.map_config.set_vision_params(enhancer.gamma, enhancer.clahe_clip)
                        print(f"Gamma: {enhancer.gamma:.1f}")
                    elif key == ord("{"):
                        enhancer.set_clahe_clip(enhancer.clahe.getClipLimit() - 0.5)
                        app.map_config.set_vision_params(enhancer.gamma, enhancer.clahe_clip)
                        print(f"CLAHE Clip: {enhancer.clahe.getClipLimit():.1f}")
                    elif key == ord("}"):
                        enhancer.set_clahe_clip(enhancer.clahe.getClipLimit() + 0.5)
                        app.map_config.set_vision_params(enhancer.gamma, enhancer.clahe_clip)
                        print(f"CLAHE Clip: {enhancer.clahe.getClipLimit():.1f}")
            finally:
                if pipeline:
                    pipeline.stop()

    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        hands.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
