import sys
import os
import cv2
import numpy as np
import mediapipe as mp
import argparse
import time
import logging

# Ensure we can import the local package
sys.path.insert(0, os.path.abspath("src"))

from light_map.camera import Camera
from light_map.common_types import MenuActions, SceneId, TokenDetectionAlgorithm
from light_map.interactive_app import InteractiveApp, AppConfig
from light_map.map_config import MapConfigManager
from light_map.calibration_logic import run_calibration_sequence
from light_map.display_utils import (
    get_screen_resolution,
    setup_logging,
    ProjectorWindow,
)
from light_map.camera_pipeline import CameraPipeline
from light_map.core.storage import StorageManager

from light_map.projector import ProjectorDistortionModel


def main():
    # 0. Basic Args setup
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
    parser.add_argument(
        "--action", type=str, help="MenuAction to execute on startup", default=None
    )
    parser.add_argument(
        "--base-dir",
        type=str,
        help="Override base directory for config and data",
        default=None,
    )
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set the logging level",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="Path to log file (relative to data dir if not absolute)",
    )
    args = parser.parse_args()

    # Initialize Storage
    storage = StorageManager(base_dir=args.base_dir)
    storage.ensure_dirs()

    # Initialize logging
    log_level = getattr(logging, args.log_level.upper())
    log_file = args.log_file
    if log_file and not os.path.isabs(log_file):
        log_file = storage.get_state_path(log_file)
    elif not log_file:
        log_file = storage.get_state_path("light_map.log")

    setup_logging(level=log_level, log_file=log_file)
    logger = logging.getLogger(__name__)

    # 1. Load Calibration
    calibration_file = storage.get_data_path("projector_calibration.npz")

    # Helper to load calibration
    def load_calib(default_screen_w, default_screen_h):
        if not os.path.exists(calibration_file):
            logger.warning(
                "%s not found. Using default camera resolution.", calibration_file
            )
            return None, 2304, 1296, None
        try:
            with np.load(calibration_file) as data:
                if "projector_matrix" not in data:
                    logger.error("Invalid calibration file (missing projector_matrix).")
                    return None, 2304, 1296, None
                matrix = data["projector_matrix"]
                if "resolution" in data:
                    w, h = data["resolution"]
                else:
                    w, h = 2304, 1296

                model = None
                if "camera_points" in data and "projector_points" in data:
                    logger.info("Loading non-linear distortion model...")
                    model = ProjectorDistortionModel(
                        matrix, data["camera_points"], data["projector_points"]
                    )

                return matrix, w, h, model
        except Exception as e:
            logger.error("Error loading calibration: %s", e, exc_info=True)
            return None, 2304, 1296, None

    native_screen_w, native_screen_h = get_screen_resolution()
    logger.info("Hardware Screen Resolution: %dx%d", native_screen_w, native_screen_h)

    transformation_matrix, cam_res_w, cam_res_h, dist_model = load_calib(
        native_screen_w, native_screen_h
    )

    if transformation_matrix is None:
        logger.info(
            "Starting uncalibrated (or using defaults). Please calibrate via menu."
        )
        # Create a dummy identity matrix if calibration missing, so app doesn't crash
        transformation_matrix = np.eye(3, dtype=np.float32)

    logger.info("Calibration loaded. Camera Resolution: %dx%d", cam_res_w, cam_res_h)

    # Register Maps
    map_sources = []
    for pattern in args.maps:
        if "," in pattern:
            map_sources.extend([p.strip() for p in pattern.split(",")])
        else:
            map_sources.append(pattern)

    if args.map:
        map_sources.append(args.map)

    # Initialize MapConfigManager early to get last_used_map
    map_config_manager = MapConfigManager(storage=storage)
    gs = map_config_manager.data.global_settings

    # 2. Setup App
    config = AppConfig(
        width=native_screen_w,
        height=native_screen_h,
        projector_matrix=transformation_matrix,
        projector_matrix_resolution=(cam_res_w, cam_res_h),
        map_search_patterns=map_sources,
        distortion_model=dist_model,
        storage_manager=storage,
        log_level=args.log_level,
        log_file=log_file,
        enable_hand_masking=gs.enable_hand_masking,
        hand_mask_padding=gs.hand_mask_padding,
        hand_mask_blur=gs.hand_mask_blur,
        gm_position=gs.gm_position,
    )
    app = InteractiveApp(config)
    app.set_debug_mode(args.debug)

    map_to_load = None
    if args.map:
        map_to_load = args.map
    elif map_config_manager.data.global_settings.last_used_map:
        last_map = map_config_manager.data.global_settings.last_used_map
        if os.path.exists(last_map):
            logger.info("Loading last used map: %s", last_map)
            map_to_load = last_map
        else:
            logger.warning("Last used map not found: %s. Clearing setting.", last_map)
            map_config_manager.data.global_settings.last_used_map = None
            map_config_manager.save()

    if map_to_load:
        if os.path.exists(map_to_load):
            logger.info("Loading map: %s", map_to_load)
            app.load_map(map_to_load, load_session=True)
        else:
            logger.error("Error: Map file not found: %s", map_to_load)

    # 3. Setup MediaPipe
    mp_hands = mp.solutions.hands
    hands = mp_hands.Hands(
        max_num_hands=2, min_detection_confidence=0.7, min_tracking_confidence=0.5
    )

    # 4. Setup Projector Window (using tkinter to hide cursor)
    window_name = "projection"
    app_win = ProjectorWindow(window_name, native_screen_w, native_screen_h)

    # 5. Main Loop
    last_processed_id = -1
    pipeline = None

    try:
        with Camera() as cam:
            # --- Resolution Mismatch Check ---
            # Verify that runtime camera resolution matches calibration resolution
            # to prevent coordinate expansion/shrinkage issues.
            cam_w, cam_h = cam.width, cam.height
            calib_w, calib_h = app.config.projector_matrix_resolution

            if calib_w > 0 and (cam_w != calib_w or cam_h != calib_h):
                msg = (
                    "\n" + "!" * 60 + "\n"
                    "CRITICAL WARNING: Camera Resolution Mismatch!\n"
                    f"  Runtime:     {cam_w}x{cam_h}\n"
                    f"  Calibration: {calib_w}x{calib_h}\n"
                    "  The projector matrix will map points incorrectly.\n"
                    "  PLEASE RE-CALIBRATE: python3 projector_calibration.py\n"
                    "!" * 60 + "\n"
                )
                logger.critical(msg)

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

                        if args.action and last_processed_id == 0:
                            logger.info("Executing Startup Action: %s", args.action)

                            # Manually Handle Actions (since process_frame doesn't ingest them)
                            if args.action == MenuActions.SCAN_SESSION:
                                if app.map_system.is_map_loaded():
                                    logger.info("Map Loaded. Starting Scan Sequence.")
                                    app.current_scene.on_exit()
                                    app.current_scene = app.scenes[SceneId.SCANNING]
                                    app.current_scene.on_enter()
                                else:
                                    logger.error(
                                        "Error: Cannot start scan. No map loaded."
                                    )

                            elif args.action == MenuActions.SCAN_ALGORITHM:
                                current = app.map_config.get_detection_algorithm()
                                new_algo = (
                                    TokenDetectionAlgorithm.STRUCTURED_LIGHT
                                    if current == TokenDetectionAlgorithm.FLASH
                                    else TokenDetectionAlgorithm.FLASH
                                )
                                logger.info(
                                    "Toggling Scan Algorithm: %s -> %s",
                                    current,
                                    new_algo,
                                )
                                app.map_config.set_detection_algorithm(new_algo)
                                # Force reload menu to update UI text if needed (though visual only)
                                if app.current_scene == app.scenes[SceneId.MENU]:
                                    app.current_scene.on_enter()

                            # Process the frame normally
                            output_image, actions = app.process_frame(
                                data.frame, data.landmarks
                            )
                        else:
                            output_image, actions = app.process_frame(
                                data.frame, data.landmarks
                            )

                        # Update Debug View if requested
                        should_hide_overlays = getattr(
                            app.current_scene, "should_hide_overlays", False
                        )
                        if app.debug_mode and not should_hide_overlays:
                            cv2.putText(
                                output_image,
                                f"Pipe FPS: {data.fps:.1f}",
                                (10, native_screen_h - 60),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                1,
                                (0, 255, 255),
                                2,
                            )

                        # D. Update Hardware Output
                        app_win.update_image(output_image)

                        # Process Actions
                        should_break = False
                        for action in actions:
                            logger.info("Executing Action: %s", action)
                            if action == MenuActions.EXIT:
                                logger.info("Exiting...")
                                should_break = True
                            elif action == MenuActions.CALIBRATE:
                                logger.info("Starting Calibration...")
                                # STOP Pipeline to free camera
                                pipeline.stop()

                                # Hide main window while calibrating
                                app_win.root.withdraw()

                                new_matrix = run_calibration_sequence(
                                    cam,
                                    projector_width=native_screen_w,
                                    projector_height=native_screen_h,
                                )

                                if new_matrix is not None:
                                    logger.info("Calibration successful! Saving...")
                                    np.savez(
                                        calibration_file,
                                        projector_matrix=new_matrix,
                                        resolution=np.array([cam.width, cam.height]),
                                        camera_resolution=np.array(
                                            [cam.width, cam.height]
                                        ),
                                        projector_resolution=np.array(
                                            [native_screen_w, native_screen_h]
                                        ),
                                    )
                                    logger.info(
                                        "Reloading application configuration..."
                                    )
                                    new_config = AppConfig(
                                        width=native_screen_w,
                                        height=native_screen_h,
                                        projector_matrix=new_matrix,
                                        projector_matrix_resolution=(
                                            cam.width,
                                            cam.height,
                                        ),
                                        log_level=args.log_level,
                                        log_file=args.log_file,
                                    )
                                    app.reload_config(new_config)
                                else:
                                    logger.warning("Calibration failed or cancelled.")

                                # Restore Window
                                app_win.root.deiconify()

                                # RESTART Pipeline
                                pipeline.start()

                            elif action == MenuActions.TOGGLE_DEBUG:
                                app.set_debug_mode(not app.debug_mode)

                        if should_break:
                            break

                    else:
                        # No new data: Just handle UI events (keyboard) and sleep
                        app_win.root.update()
                        time.sleep(0.001)

                    # F. Handle Keyboard Interrupts (Check every loop iteration)
                    key = app_win.get_key()
                    if key == -1:
                        # Fallback to OpenCV waitKey for debug windows if any
                        key = cv2.waitKey(1) & 0xFF
                        if key == 0xFF:
                            key = -1

                    if key == ord("q"):
                        break
                    elif key == ord("d"):
                        app.set_debug_mode(not app.debug_mode)

                    if app_win.is_closed():
                        break

            except Exception as e:
                logger.critical(
                    "An unhandled error occurred in the main loop: %s", e, exc_info=True
                )
            finally:
                if pipeline:
                    pipeline.stop()

                # Save session (tokens and viewport) before exiting
                if app.map_system.is_map_loaded():
                    app.save_session()

    except Exception as e:
        logger.critical(
            "An unhandled error occurred during camera setup: %s", e, exc_info=True
        )
    finally:
        hands.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
