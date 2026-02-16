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
from light_map.common_types import MenuActions
from light_map.interactive_app import InteractiveApp, AppConfig
from light_map.map_config import MapConfigManager
from light_map.calibration_logic import run_calibration_sequence
from light_map.camera_pipeline import CameraPipeline


def main():
    parser = argparse.ArgumentParser(description="Hand Tracker & Menu System")
    parser.add_argument(
        "--debug", action="store_true", help="Enable debug overlay", default=False
    )
    parser.add_argument(
        "--maps", nargs="+", help="List of map files or globs to register", default=[]
    )
    parser.add_argument(
        "--map", type=str, help="Path to SVG map file to load (legacy)", default=None
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

    # Register Maps
    map_sources = args.maps
    if args.map:
        map_sources.append(args.map)

    # Initialize MapConfigManager early to get last_used_map
    map_config_manager = MapConfigManager()

    # 2. Setup App
    config = AppConfig(
        width=screen_w,
        height=screen_h,
        projector_matrix=transformation_matrix,
        map_search_patterns=map_sources,
    )
    app = InteractiveApp(config)
    app.set_debug_mode(args.debug)

    map_to_load = None
    if args.map:
        map_to_load = args.map
    elif map_config_manager.data.global_settings.last_used_map:
        last_map = map_config_manager.data.global_settings.last_used_map
        if os.path.exists(last_map):
            print(f"Loading last used map: {last_map}")
            map_to_load = last_map
        else:
            print(f"Last used map not found: {last_map}. Clearing setting.")
            map_config_manager.data.global_settings.last_used_map = None
            map_config_manager.save()

    if map_to_load:
        if os.path.exists(map_to_load):
            print(f"Loading map: {map_to_load}")
            app.load_map(map_to_load)
        else:
            print(f"Error: Map file not found: {map_to_load}")

    # 3. Setup MediaPipe
    mp_hands = mp.solutions.hands
    hands = mp_hands.Hands(
        max_num_hands=2, min_detection_confidence=0.7, min_tracking_confidence=0.5
    )

    # 4. Setup Projector Window
    window_name = "projection"
    cv2.namedWindow(window_name, cv2.WND_PROP_FULLSCREEN)
    cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    # 5. Main Loop
    last_processed_id = -1
    pipeline = None

    try:
        with Camera() as cam:
            # Initialize Pipeline
            pipeline = CameraPipeline(cam, hands)
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

                        # C. Orchestrate Logic
                        output_image, actions = app.process_frame(
                            data.frame, data.landmarks
                        )

                        # Update Debug View if requested
                        if app.debug_mode:
                            cv2.putText(
                                output_image,
                                f"Pipe FPS: {data.fps:.1f}",
                                (10, screen_h - 60),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                1,
                                (0, 255, 255),
                                2,
                            )

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
                                    )
                                    app.reload_config(new_config)
                                else:
                                    print("Calibration failed or cancelled.")

                                # Restore Window
                                cv2.namedWindow(window_name, cv2.WND_PROP_FULLSCREEN)
                                cv2.setWindowProperty(
                                    window_name,
                                    cv2.WND_PROP_FULLSCREEN,
                                    cv2.WINDOW_FULLSCREEN,
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
