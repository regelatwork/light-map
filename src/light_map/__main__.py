import sys
import os
import cv2
import signal
import numpy as np
import argparse
import time
import logging
import multiprocessing as mp

from .camera import Camera
from .common_types import Action, MenuActions, SceneId, TokenDetectionAlgorithm
from .interactive_app import InteractiveApp, AppConfig
from .map_config import MapConfigManager
from .display_utils import (
    get_screen_resolution,
    setup_logging,
    ProjectorWindow,
)
from .core.storage import StorageManager

from .projector import ProjectorDistortionModel
import threading
from .vision.process_manager import VisionProcessManager
from .core.main_loop import MainLoopController
from .vision.frame_producer import FrameProducer
from .input_manager import InputManager


def camera_capture_loop(cam, operator, stop_event):
    while not stop_event.is_set():
        frame = cam.read()
        if frame is not None:
            operator._publish_frame(frame, time.perf_counter_ns())
        else:
            time.sleep(0.01)


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
    # Remote Driver Args
    parser.add_argument(
        "--remote-hands",
        type=str,
        choices=["exclusive", "merge", "ignore"],
        default="ignore",
        help="Mode for remote hand inputs",
    )
    parser.add_argument(
        "--remote-tokens",
        type=str,
        choices=["exclusive", "merge", "ignore"],
        default="ignore",
        help="Mode for remote token inputs",
    )
    parser.add_argument(
        "--remote-port",
        type=int,
        default=8000,
        help="Port for the remote driver HTTP API",
    )
    args = parser.parse_args()

    # Initialize Multiprocessing Manager for shared state mirror
    mp_manager = mp.Manager()
    state_mirror = mp_manager.dict()
    state_mirror["config"] = {}
    state_mirror["world"] = {}
    state_mirror["tokens"] = []
    state_mirror["menu"] = None

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

    main_loop = None

    # Signal handling for graceful shutdown
    def signal_handler(sig, frame):
        sig_name = signal.Signals(sig).name
        logger.info(f"Received {sig_name}. Triggering graceful shutdown...")
        if main_loop:
            main_loop.stop()
        else:
            sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Ensure all unhandled exceptions are logged
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.critical(
            "Unhandled exception", exc_info=(exc_type, exc_value, exc_traceback)
        )

    sys.excepthook = handle_exception

    def handle_thread_exception(args):
        logger.critical(
            "Unhandled exception in thread",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    threading.excepthook = handle_thread_exception

    # 1. Load Calibration
    calibration_file = storage.get_data_path("projector_calibration.npz")
    intrinsics_path = storage.get_data_path("camera_calibration.npz")
    extrinsics_path = storage.get_data_path("camera_extrinsics.npz")

    # Helper to load calibration
    def load_calib(default_screen_w, default_screen_h):
        if not os.path.exists(calibration_file):
            msg = (
                "\n" + "!" * 60 + "\n"
                "CRITICAL ERROR: Projector Calibration Missing!\n"
                f"  File not found: {calibration_file}\n"
                "  The system cannot project correctly without this.\n"
                "  PLEASE RUN: python3 scripts/projector_calibration.py\n"
                "!" * 60 + "\n"
            )
            logger.critical(msg)
            sys.exit(1)
        try:
            with np.load(calibration_file) as data:
                if "projector_matrix" not in data:
                    logger.error("Invalid calibration file (missing projector_matrix).")
                    return None, 4608, 2592, None
                matrix = data["projector_matrix"]
                if "resolution" in data:
                    w, h = data["resolution"]
                else:
                    w, h = 4608, 2592

                model = None
                if "camera_points" in data and "projector_points" in data:
                    logger.info("Loading non-linear distortion model...")
                    model = ProjectorDistortionModel(
                        matrix, data["camera_points"], data["projector_points"]
                    )

                return matrix, w, h, model
        except Exception as e:
            logger.error("Error loading calibration: %s", e, exc_info=True)
            return None, 4608, 2592, None

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

    # Detect runtime camera resolution first
    cam_w, cam_h = 0, 0
    with Camera() as cam:
        cam_w, cam_h = cam.width, cam.height

    # 2. Setup App
    config = AppConfig(
        width=native_screen_w,
        height=native_screen_h,
        projector_matrix=transformation_matrix,
        projector_matrix_resolution=(cam_res_w, cam_res_h),
        camera_resolution=(cam_w, cam_h),
        map_search_patterns=map_sources,
        distortion_model=dist_model,
        storage_manager=storage,
        log_level=args.log_level,
        log_file=log_file,
        enable_hand_masking=gs.enable_hand_masking,
        hand_mask_padding=gs.hand_mask_padding,
        gm_position=gs.gm_position,
        projector_ppi=gs.projector_ppi,
        inspection_linger_duration=gs.inspection_linger_duration,
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

    # 3. Setup Projector Window (using tkinter to hide cursor)
    window_name = "projection"
    app_win = ProjectorWindow(window_name, native_screen_w, native_screen_h)

    # 5. Main Loop
    startup_action_executed = False

    try:
        with Camera() as cam:
            # --- Resolution Mismatch Check ---
            cam_w, cam_h = cam.width, cam.height
            calib_w, calib_h = app.config.projector_matrix_resolution

            if calib_w > 0 and (cam_w != calib_w or cam_h != calib_h):
                msg = (
                    "\n" + "!" * 60 + "\n"
                    "CRITICAL WARNING: Camera Resolution Mismatch!\n"
                    f"  Runtime:     {cam_w}x{cam_h}\n"
                    f"  Calibration: {calib_w}x{calib_h}\n"
                    "  The projector matrix will map points incorrectly.\n"
                    "  PLEASE RE-CALIBRATE: python3 scripts/projector_calibration.py\n"
                    "!" * 60 + "\n"
                )
                logger.critical(msg)

            # Populate initial config mirror
            state_mirror["config"] = {
                "cam_res": (cam_w, cam_h),
                "proj_res": (native_screen_w, native_screen_h),
                "remote_hands": args.remote_hands,
                "remote_tokens": args.remote_tokens,
                "remote_port": args.remote_port,
            }

            # Start Process Manager
            manager = VisionProcessManager(
                width=cam_w,
                height=cam_h,
                num_consumers=2,
                projector_matrix=app.config.projector_matrix,
                map_dims=(app.config.width, app.config.height),
                intrinsics_path=intrinsics_path,
                extrinsics_path=extrinsics_path,
                camera_matrix=app.app_context.camera_matrix,
                dist_coeffs=app.app_context.dist_coeffs,
                remote_mode_hands=args.remote_hands,
                remote_mode_tokens=args.remote_tokens,
                remote_port=args.remote_port,
                state_mirror=state_mirror,
            )
            manager.start()

            # Use the WorldState instance from InteractiveApp
            state = app.state
            producer = FrameProducer(
                shm_name=manager.shm_name, width=cam_w, height=cam_h
            )
            producer.lock = manager.lock

            input_manager = InputManager(
                flicker_timeout=1.5, time_provider=app.time_provider
            )
            main_loop = MainLoopController(
                state,
                manager,
                input_manager,
                producer,
                aruco_mapper=app.aruco_mapper,
                state_mirror=state_mirror,
                events=app.events,
                time_provider=app.time_provider,
            )

            stop_event = threading.Event()
            cam_thread = threading.Thread(
                target=camera_capture_loop, args=(cam, manager.operator, stop_event)
            )
            cam_thread.start()

            def render_cb(state, actions):
                nonlocal startup_action_executed

                # A. Update State Mirror for Remote Driver
                if state_mirror is not None:
                    state_mirror["config"] = {
                        "cam_res": (cam_w, cam_h),
                        "proj_res": (native_screen_w, native_screen_h),
                        "remote_hands": args.remote_hands,
                        "remote_tokens": args.remote_tokens,
                        "remote_port": args.remote_port,
                        "enable_hand_masking": app.config.enable_hand_masking,
                        "gm_position": str(app.config.gm_position),
                        "debug_mode": app.debug_mode,
                        "fow_disabled": app.fow_manager.is_disabled
                        if app.fow_manager
                        else True,
                    }

                # B. Handle Startup Actions (Execute once)
                if args.action and not startup_action_executed:
                    logger.info("Executing Startup Action: %s", args.action)
                    startup_action_executed = True

                    if args.action == MenuActions.SCAN_SESSION:
                        if app.map_system.is_map_loaded():
                            logger.info("Map Loaded. Starting Scan Sequence.")
                            app.current_scene.on_exit()
                            app.current_scene = app.scenes[SceneId.SCANNING]
                            app.current_scene.on_enter()
                        else:
                            logger.error("Error: Cannot start scan. No map loaded.")

                    elif args.action == MenuActions.SCAN_ALGORITHM:
                        current = app.map_config.get_detection_algorithm()
                        new_algo = (
                            TokenDetectionAlgorithm.STRUCTURED_LIGHT
                            if current == TokenDetectionAlgorithm.FLASH
                            else TokenDetectionAlgorithm.FLASH
                        )
                        logger.info(
                            "Toggling Scan Algorithm: %s -> %s", current, new_algo
                        )
                        app.map_config.set_detection_algorithm(new_algo)
                        if app.current_scene == app.scenes[SceneId.MENU]:
                            app.current_scene.on_enter()

                # C. Process and Render
                main_loop.debug_mode = app.debug_mode
                output_image, scene_actions = app.process_state(state, actions)

                did_render = False
                if output_image is not None:
                    did_render = True
                    # Update Debug View if requested
                    should_hide_overlays = getattr(
                        app.current_scene, "should_hide_overlays", False
                    )
                    if app.debug_mode and not should_hide_overlays:
                        cv2.putText(
                            output_image,
                            f"FPS: {app.fps:.1f}",
                            (10, native_screen_h - 60),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            1,
                            (0, 255, 255),
                            2,
                        )

                    # D. Update Hardware Output
                    app_win.update_image(output_image)

                # E. Process Actions
                should_break = False
                for action in scene_actions + actions:
                    if hasattr(action, "value"):  # Check if enum
                        try:
                            action_str = action.value
                        except Exception:
                            action_str = str(action)
                    else:
                        action_str = action

                    if action_str == MenuActions.EXIT or action_str == Action.QUIT:
                        logger.info("Exiting...")
                        should_break = True
                    elif action_str == MenuActions.CALIBRATE:
                        logger.info("Starting Calibration...")
                        should_break = True
                    elif (
                        action_str == MenuActions.TOGGLE_DEBUG
                        or action_str == Action.TOGGLE_DEBUG
                    ):
                        app.set_debug_mode(not app.debug_mode)

                if should_break:
                    logger.info(f"Stopping main loop due to action: {action_str}")
                    main_loop.stop()

                if app_win.is_closed():
                    logger.info("Stopping main loop because window is closed.")
                    main_loop.stop()

                return did_render

            try:
                main_loop.run(render_cb)
            except Exception as e:
                logger.critical(
                    "An unhandled error occurred in the main loop: %s", e, exc_info=True
                )
            finally:
                # 1. Stop Camera Producer Thread FIRST
                stop_event.set()
                cam_thread.join(timeout=2.0)

                # 2. Save Session
                if app.map_system.is_map_loaded():
                    app.save_session()

                # 3. Stop Main Loop and Vision Processes
                main_loop.stop()

    except Exception as e:
        logger.critical(
            "An unhandled error occurred during camera setup: %s", e, exc_info=True
        )
    finally:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
