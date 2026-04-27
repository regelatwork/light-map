import sys
import os
import cv2
import signal
import numpy as np
import argparse
import time
import logging
import multiprocessing as mp
import threading

from light_map.vision.infrastructure.camera import Camera
from light_map.core.common_types import (
    Action,
    MenuActions,
    SceneId,
    TokenDetectionAlgorithm,
)
from light_map.interactive_app import InteractiveApp, AppConfig
from light_map.map.map_config import MapConfigManager
from light_map.core.display_utils import (
    get_screen_resolution,
    setup_logging,
    ProjectorWindow,
)
from light_map.core.storage import StorageManager
from light_map.rendering.projector import ProjectorDistortionModel
from light_map.vision.infrastructure.process_manager import VisionProcessManager
from light_map.core.main_loop import MainLoopController
from light_map.vision.infrastructure.frame_producer import FrameProducer
from light_map.input.input_manager import InputManager

# Import calibration functions from scripts (these will be renamed/moved later)
# For now we use relative imports if possible, or we might need to add scripts to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
try:
    from calibrate import run_calibrate
    from projector_calibration import run_projector_calibrate
except ImportError:
    # If scripts are not available (e.g. in some build environments), provide stubs
    def run_calibrate(args):
        print("Error: Camera calibration script not found.")
        sys.exit(1)

    def run_projector_calibrate(args):
        print("Error: Projector calibration script not found.")
        sys.exit(1)


def camera_capture_loop(camera, operator, stop_event):
    while not stop_event.is_set():
        frame = camera.read()
        if frame is not None:
            operator._publish_frame(frame, time.perf_counter_ns())
        else:
            time.sleep(0.01)


def run_app(args):
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
    def load_calibration(default_screen_width, default_screen_height):
        if not os.path.exists(calibration_file):
            msg = (
                "\n" + "!" * 60 + "\n"
                "CRITICAL ERROR: Projector Calibration Missing!\n"
                f"  File not found: {calibration_file}\n"
                "  The system cannot project correctly without this.\n"
                "  PLEASE RUN: light-map projector-calibrate\n"
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
                    width, height = data["resolution"]
                else:
                    width, height = 4608, 2592

                model = None
                if "camera_points" in data and "projector_points" in data:
                    logger.info("Loading non-linear distortion model...")
                    model = ProjectorDistortionModel(
                        matrix, data["camera_points"], data["projector_points"]
                    )

                return matrix, width, height, model
        except Exception as e:
            logger.error("Error loading calibration: %s", e, exc_info=True)
            return None, 4608, 2592, None

    native_screen_width, native_screen_height = get_screen_resolution()
    logger.info(
        "Hardware Screen Resolution: %dx%d", native_screen_width, native_screen_height
    )

    transformation_matrix, camera_res_width, camera_res_height, distortion_model = (
        load_calibration(native_screen_width, native_screen_height)
    )

    if transformation_matrix is None:
        logger.info(
            "Starting uncalibrated (or using defaults). Please calibrate via menu."
        )
        # Create a dummy identity matrix if calibration missing, so app doesn't crash
        transformation_matrix = np.eye(3, dtype=np.float32)

    logger.info(
        "Calibration loaded. Camera Resolution: %dx%d",
        camera_res_width,
        camera_res_height,
    )

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

    # Load Camera Calibration for Parallax Correction
    camera_matrix = None
    distortion_coefficients = None
    if os.path.exists(intrinsics_path):
        with np.load(intrinsics_path) as data:
            camera_matrix = data["camera_matrix"]
            distortion_coefficients = data.get("distortion_coefficients")
            if distortion_coefficients is None:
                distortion_coefficients = data.get("dist_coeffs")

    rotation_vector, translation_vector = None, None
    if os.path.exists(extrinsics_path):
        with np.load(extrinsics_path) as data:
            rotation_vector = data.get("rotation_vector")
            if rotation_vector is None:
                rotation_vector = data.get("rvec")
            translation_vector = data.get("translation_vector")
            if translation_vector is None:
                translation_vector = data.get("tvec")

    # Detect runtime camera resolution first
    runtime_camera_width, runtime_camera_height = 0, 0
    with Camera() as cam:
        runtime_camera_width, runtime_camera_height = cam.width, cam.height

    # 2. Setup App
    config = AppConfig(
        width=native_screen_width,
        height=native_screen_height,
        projector_matrix=transformation_matrix,
        projector_matrix_resolution=(camera_res_width, camera_res_height),
        camera_resolution=(runtime_camera_width, runtime_camera_height),
        camera_matrix=camera_matrix,
        distortion_coefficients=distortion_coefficients,
        rotation_vector=rotation_vector,
        translation_vector=translation_vector,
        map_search_patterns=map_sources,
        distortion_model=distortion_model,
        storage_manager=storage,
        log_level=args.log_level,
        log_file=log_file,
        enable_hand_masking=gs.enable_hand_masking,
        hand_mask_padding=gs.hand_mask_padding,
        enable_aruco_masking=gs.enable_aruco_masking,
        aruco_mask_padding=gs.aruco_mask_padding,
        gm_position=gs.gm_position,
        projector_ppi=gs.projector_ppi,
        aruco_defaults=gs.aruco_defaults,
        token_profiles=gs.token_profiles,
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

    # 5. Main Loop
    startup_action_executed = False

    try:
        with (
            Camera() as cam,
            ProjectorWindow(
                window_name, native_screen_width, native_screen_height
            ) as app_win,
        ):
            # --- Resolution Mismatch Check ---
            current_camera_width, current_camera_height = cam.width, cam.height
            calibrated_width, calibrated_height = app.config.projector_matrix_resolution

            if calibrated_width > 0 and (
                current_camera_width != calibrated_width
                or current_camera_height != calibrated_height
            ):
                msg = (
                    "\n" + "!" * 60 + "\n"
                    "CRITICAL WARNING: Camera Resolution Mismatch!\n"
                    f"  Runtime:     {current_camera_width}x{current_camera_height}\n"
                    f"  Calibration: {calibrated_width}x{calibrated_height}\n"
                    "  The projector matrix will map points incorrectly.\n"
                    "  PLEASE RE-CALIBRATE: light-map projector-calibrate\n"
                    "!" * 60 + "\n"
                )
                logger.critical(msg)

            # Populate initial config mirror
            state_mirror["config"] = {
                "cam_res": (current_camera_width, current_camera_height),
                "proj_res": (native_screen_width, native_screen_height),
                "remote_hands": args.remote_hands,
                "remote_tokens": args.remote_tokens,
                "remote_host": args.remote_host,
                "remote_port": args.remote_port,
                "enable_hand_masking": app.config.enable_hand_masking,
                "enable_aruco_masking": app.config.enable_aruco_masking,
                "aruco_mask_intensity": app.config.aruco_mask_intensity,
                "pointer_offset_mm": app.config.pointer_offset_mm,
                "gm_position": str(app.config.gm_position),
                "debug_mode": app.debug_mode,
                "fow_disabled": app.fow_manager.is_disabled
                if app.fow_manager
                else True,
                "current_map_path": app.current_map_path,
                "projector_ppi": app.config.projector_ppi,
                "map_width": app.map_system.svg_loader.width
                if app.map_system.svg_loader
                else 0.0,
                "map_height": app.map_system.svg_loader.height
                if app.map_system.svg_loader
                else 0.0,
                "token_profiles": {
                    k: {"size": v.size, "height_mm": v.height_mm}
                    for k, v in app.map_config.data.global_settings.token_profiles.items()
                },
                "aruco_defaults": {
                    str(k): {
                        "name": v.name,
                        "type": v.type,
                        "profile": v.profile,
                        "size": v.size,
                        "height_mm": v.height_mm,
                        "color": v.color,
                    }
                    for k, v in app.map_config.data.global_settings.aruco_defaults.items()
                },
            }

            # Populate initial state mirror for world, tokens, and menu
            state_mirror["world"] = app.state.to_dict()
            state_mirror["tokens"] = [t.to_dict() for t in app.state.tokens]
            if app.state.menu_state:
                state_mirror["menu"] = {
                    "title": app.state.menu_state.current_menu_title,
                    "depth": len(
                        getattr(app.state.menu_state, "node_stack_titles", [])
                    ),
                    "items": [item.title for item in app.state.menu_state.active_items],
                }
            else:
                state_mirror["menu"] = None

            # Populate initial maps list
            state_mirror["maps"] = {
                path: {
                    "name": os.path.basename(path),
                    "aruco_overrides": {
                        str(aid): {
                            "name": v.name,
                            "type": v.type,
                            "profile": v.profile,
                            "size": v.size,
                            "height_mm": v.height_mm,
                            "color": v.color,
                        }
                        for aid, v in entry.aruco_overrides.items()
                    },
                }
                for path, entry in app.map_config.data.maps.items()
            }

            # Calculate number of consumers for the camera frames
            # 1 for ArucoWorker, 1 for HandWorker, 1 for RemoteDriverWorker if enabled
            active_consumers = 0
            if args.remote_tokens != "exclusive":
                active_consumers += 1
            if args.remote_hands != "exclusive":
                active_consumers += 1
            if args.remote_hands != "ignore" or args.remote_tokens != "ignore":
                active_consumers += 1

            # Start Process Manager
            with VisionProcessManager(
                width=current_camera_width,
                height=current_camera_height,
                num_consumers=active_consumers,
                projector_matrix=app.config.projector_matrix,
                map_dims=(app.config.width, app.config.height),
                intrinsics_path=intrinsics_path,
                extrinsics_path=extrinsics_path,
                camera_matrix=app.config.camera_matrix,
                distortion_coefficients=app.config.distortion_coefficients,
                remote_mode_hands=args.remote_hands,
                remote_mode_tokens=args.remote_tokens,
                remote_host=args.remote_host,
                remote_port=args.remote_port,
                remote_origins=args.remote_origins,
                state_mirror=state_mirror,
            ) as manager:
                # Use the WorldState instance from InteractiveApp
                state = app.state
                producer = FrameProducer(
                    shm_name=manager.shm_name,
                    width=current_camera_width,
                    height=current_camera_height,
                    num_consumers=active_consumers,
                )
                producer.lock = manager.lock

                input_manager = InputManager(
                    flicker_timeout=1.5,
                    time_provider=app.time_provider,
                    events=app.events,
                )
                with MainLoopController(
                    state,
                    manager,
                    input_manager,
                    producer,
                    aruco_mapper=app.aruco_mapper,
                    state_mirror=state_mirror,
                    events=app.events,
                    time_provider=app.time_provider,
                ) as ml:
                    main_loop = ml

                    stop_event = threading.Event()
                    cam_thread = threading.Thread(
                        target=camera_capture_loop,
                        args=(cam, manager.operator, stop_event),
                    )
                    cam_thread.start()

                    last_map_config_version = -1
                    last_debug_mode = None
                    last_map_path = None
                    last_fow_disabled = None
                    last_gm_position = None
                    last_hand_masking = None
                    last_aruco_masking = None
                    last_world_ts = -1
                    last_tokens_ts = -1
                    last_menu_ts = -1
                    last_projector_pose_ts = -1
                    last_config_ts = -1
                    last_aruco_intensity = -1
                    last_aruco_persistence = -1
                    last_pointer_offset = -1
                    last_tactical_ts = -1

                    def render_cb(state, actions):
                        nonlocal \
                            startup_action_executed, \
                            last_map_config_version, \
                            last_debug_mode, \
                            last_map_path, \
                            last_fow_disabled, \
                            last_gm_position, \
                            last_hand_masking, \
                            last_aruco_masking, \
                            last_world_ts, \
                            last_tokens_ts, \
                            last_menu_ts, \
                            last_projector_pose_ts, \
                            last_config_ts, \
                            last_aruco_intensity, \
                            last_aruco_persistence, \
                            last_pointer_offset, \
                            last_tactical_ts

                        # A. Handle Startup Actions (Execute once)
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
                                if app.current_scene == app.scenes[SceneId.MENU]:
                                    app.current_scene.on_enter()

                        if not state.is_running:
                            logger.info("Shutdown requested via state.is_running")
                            return False

                        # B. Process and Render
                        main_loop.debug_mode = app.debug_mode
                        output_image, scene_actions = app.process_state(state, actions)

                        if output_image is not None:
                            # Update Debug View if requested
                            should_hide_overlays = getattr(
                                app.current_scene, "should_hide_overlays", False
                            )
                            if app.debug_mode and not should_hide_overlays:
                                cv2.putText(
                                    output_image,
                                    f"FPS: {app.fps:.1f}",
                                    (10, native_screen_height - 60),
                                    cv2.FONT_HERSHEY_SIMPLEX,
                                    1,
                                    (0, 255, 255),
                                    2,
                                )

                            # C. Update Hardware Output
                            app_win.update_image(output_image)

                        # D. Update State Mirror for Remote Driver (AFTER process_state)
                        if state_mirror is not None:
                            # 1. Update Frequent State (World, Tokens, Menu) if they changed
                            # WorldState tracks granular timestamps for all components
                            current_world_ts = max(
                                state.scene_version,
                                state.viewport_version,
                                state.hands_version,
                                state.fow_version,
                                state.visibility_version,
                                state.map_version,
                                state.menu_version,
                                state.tokens_version,
                                state.notifications_version,
                            )

                            if current_world_ts != last_world_ts:
                                state_mirror["world"] = state.to_dict()
                                last_world_ts = current_world_ts

                            if state.tokens_version != last_tokens_ts:
                                state_mirror["tokens"] = [
                                    t.to_dict() for t in state.tokens
                                ]
                                last_tokens_ts = state.tokens_version

                            if state.menu_version != last_menu_ts:
                                if state.menu_state:
                                    state_mirror["menu"] = {
                                        "title": state.menu_state.current_menu_title,
                                        "depth": len(
                                            getattr(
                                                state.menu_state,
                                                "node_stack_titles",
                                                [],
                                            )
                                        ),
                                        "items": [
                                            item.title
                                            for item in state.menu_state.active_items
                                        ],
                                    }
                                else:
                                    state_mirror["menu"] = None
                                last_menu_ts = state.menu_version

                            if state.tactical_bonuses_version != last_tactical_ts:
                                state_mirror["tactical_bonuses"] = state.tactical_bonuses
                                last_tactical_ts = state.tactical_bonuses_version

                            # 2. Update Configuration (Only if changed)
                            current_map_config_version = getattr(
                                app.map_config, "version", 0
                            )
                            fow_disabled = (
                                app.fow_manager.is_disabled if app.fow_manager else True
                            )

                            if (
                                current_map_config_version != last_map_config_version
                                or state.projector_pose_version
                                != last_projector_pose_ts
                                or state.config_version != last_config_ts
                                or app.debug_mode != last_debug_mode
                                or app.current_map_path != last_map_path
                                or fow_disabled != last_fow_disabled
                                or str(app.config.gm_position) != last_gm_position
                                or app.config.enable_hand_masking != last_hand_masking
                                or app.config.enable_aruco_masking != last_aruco_masking
                                or app.config.aruco_mask_intensity
                                != last_aruco_intensity
                                or app.config.aruco_mask_persistence_s
                                != last_aruco_persistence
                                or app.config.pointer_offset_mm != last_pointer_offset
                            ):
                                last_projector_pose_ts = state.projector_pose_version
                                last_config_ts = state.config_version
                                last_aruco_intensity = app.config.aruco_mask_intensity
                                last_aruco_persistence = (
                                    app.config.aruco_mask_persistence_s
                                )
                                last_pointer_offset = app.config.pointer_offset_mm
                                calibrated_pos = app.config.projector_3d_model.calibrated_projector_center
                                state_mirror["config"] = {
                                    "cam_res": (
                                        current_camera_width,
                                        current_camera_height,
                                    ),
                                    "proj_res": (
                                        native_screen_width,
                                        native_screen_height,
                                    ),
                                    "calibrated_projector_pos": calibrated_pos.tolist()
                                    if calibrated_pos is not None
                                    else None,
                                    "current_projector_pos": state.projector_pose.to_list(),
                                    "remote_hands": args.remote_hands,
                                    "remote_tokens": args.remote_tokens,
                                    "remote_port": args.remote_port,
                                    "enable_hand_masking": app.config.enable_hand_masking,
                                    "enable_aruco_masking": app.config.enable_aruco_masking,
                                    "aruco_mask_intensity": app.config.aruco_mask_intensity,
                                    "aruco_mask_persistence_s": app.config.aruco_mask_persistence_s,
                                    "pointer_offset_mm": app.config.pointer_offset_mm,
                                    "gm_position": str(app.config.gm_position),
                                    "debug_mode": app.debug_mode,
                                    "fow_disabled": fow_disabled,
                                    "projector_ppi": app.config.projector_ppi,
                                    "current_map_path": app.current_map_path,
                                    "map_width": app.map_system.svg_loader.width
                                    if app.map_system.svg_loader
                                    else 0.0,
                                    "map_height": app.map_system.svg_loader.height
                                    if app.map_system.svg_loader
                                    else 0.0,
                                    "token_profiles": {
                                        k: {"size": v.size, "height_mm": v.height_mm}
                                        for k, v in app.map_config.data.global_settings.token_profiles.items()
                                    },
                                    "aruco_defaults": {
                                        str(k): {
                                            "name": v.name,
                                            "type": v.type,
                                            "profile": v.profile,
                                            "size": v.size,
                                            "height_mm": v.height_mm,
                                            "color": v.color,
                                        }
                                        for k, v in app.map_config.data.global_settings.aruco_defaults.items()
                                    },
                                }

                                # 3. Update Map List (if map config changed)
                                if (
                                    current_map_config_version
                                    != last_map_config_version
                                ):
                                    state_mirror["maps"] = {
                                        path: {
                                            "name": os.path.basename(path),
                                            "aruco_overrides": {
                                                str(aid): {
                                                    "name": v.name,
                                                    "type": v.type,
                                                    "profile": v.profile,
                                                    "size": v.size,
                                                    "height_mm": v.height_mm,
                                                    "color": v.color,
                                                }
                                                for aid, v in entry.aruco_overrides.items()
                                            },
                                        }
                                        for path, entry in app.map_config.data.maps.items()
                                    }
                                    last_map_config_version = current_map_config_version

                                last_debug_mode = app.debug_mode
                                last_map_path = app.current_map_path
                                last_fow_disabled = fow_disabled
                                last_gm_position = str(app.config.gm_position)
                                last_hand_masking = app.config.enable_hand_masking
                                last_aruco_masking = app.config.enable_aruco_masking
                                last_aruco_persistence = (
                                    app.config.aruco_mask_persistence_s
                                )

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

                            if (
                                action_str == MenuActions.EXIT
                                or action_str == Action.QUIT
                            ):
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
                            logger.info(
                                f"Stopping main loop due to action: {action_str}"
                            )
                            main_loop.stop()

                        if app_win.is_closed():
                            logger.info("Stopping main loop because window is closed.")
                            main_loop.stop()

                        return True

                    try:
                        main_loop.run(render_cb)
                    except Exception as e:
                        logger.critical(
                            "An unhandled error occurred in the main loop: %s",
                            e,
                            exc_info=True,
                        )
                    finally:
                        # 1. Stop Camera Producer Thread
                        stop_event.set()
                        cam_thread.join(timeout=2.0)

                        # 2. Save Session
                        if app.map_system.is_map_loaded():
                            app.save_session()

    except Exception as e:
        logger.critical(
            "An unhandled error occurred during application lifecycle: %s",
            e,
            exc_info=True,
        )
    finally:
        cv2.destroyAllWindows()


def main():
    # Parent parser for common arguments
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument(
        "--base-dir",
        type=str,
        help="Override base directory for config and data",
        default=None,
    )
    parent_parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set the logging level",
    )
    parent_parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="Path to log file (relative to data dir if not absolute)",
    )

    parser = argparse.ArgumentParser(description="Light Map AR Tabletop Platform")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # 'run' command (default)
    run_parser = subparsers.add_parser(
        "run", parents=[parent_parser], help="Run the main application"
    )
    run_parser.add_argument(
        "--debug", action="store_true", help="Enable debug overlay", default=False
    )
    run_parser.add_argument(
        "--maps", nargs="+", help="List of map files or globs to register", default=[]
    )
    run_parser.add_argument(
        "--map", type=str, help="Path to SVG map file to load (legacy)", default=None
    )
    run_parser.add_argument(
        "--action", type=str, help="MenuAction to execute on startup", default=None
    )
    run_parser.add_argument(
        "--remote-hands",
        type=str,
        choices=["exclusive", "merge", "ignore"],
        default="ignore",
        help="Mode for remote hand inputs",
    )
    run_parser.add_argument(
        "--remote-tokens",
        type=str,
        choices=["exclusive", "merge", "ignore"],
        default="ignore",
        help="Mode for remote token inputs",
    )
    run_parser.add_argument(
        "--remote-port",
        type=int,
        default=8000,
        help="Port for the remote driver HTTP API",
    )
    run_parser.add_argument(
        "--remote-host",
        type=str,
        default="127.0.0.1",
        help="Host address for the remote driver HTTP API",
    )
    run_parser.add_argument(
        "--remote-origins",
        nargs="+",
        help="Allowed CORS origins for remote driver",
        default=None,
    )

    # 'calibrate' command
    calibrate_parser = subparsers.add_parser(
        "calibrate", parents=[parent_parser], help="Run camera intrinsics calibration"
    )
    calibrate_parser.add_argument(
        "--image-dir",
        type=str,
        help="Directory containing calibration images",
        default="./images",
    )

    # 'projector-calibrate' command
    proj_calibrate_parser = subparsers.add_parser(
        "projector-calibrate",
        parents=[parent_parser],
        help="Run projector-camera calibration",
    )
    proj_calibrate_parser.add_argument(
        "--steps",
        nargs="+",
        choices=["projector", "ppi", "extrinsics"],
        default=["projector", "ppi", "extrinsics"],
        help="Calibration steps to run (default: all)",
    )

    # Version command
    subparsers.add_parser("version", help="Show version information")

    # Default to 'run' if no command provided
    if len(sys.argv) == 1:
        args = parser.parse_args(["run"])
    elif sys.argv[1] not in subparsers.choices and not sys.argv[1].startswith("-"):
        # This is for backward compatibility where people might just pass --debug etc.
        args = parser.parse_args(["run"] + sys.argv[1:])
    elif sys.argv[1].startswith("-") and sys.argv[1] not in ["-h", "--help"]:
        # Also for backward compatibility: if first arg is an option, assume 'run'
        args = parser.parse_args(["run"] + sys.argv[1:])
    else:
        args = parser.parse_args()

    if args.command == "run":
        run_app(args)
    elif args.command == "calibrate":
        # We need to monkeypatch sys.argv for the script's own parser if it uses one
        # but our run_calibrate already takes args if we modify it.
        # Let's check how we called it.
        # Actually, let's just call it.
        run_calibrate(args)
    elif args.command == "projector-calibrate":
        run_projector_calibrate(args)
    elif args.command == "version":
        import pkg_resources

        try:
            version = pkg_resources.get_distribution("light-map").version
            print(f"Light Map version {version}")
        except Exception:
            print("Light Map (development version)")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
