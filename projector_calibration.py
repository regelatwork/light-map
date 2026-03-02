import sys
import os
import numpy as np
import logging
import argparse
import cv2
import time
import math

# Ensure we can import the local package
sys.path.insert(0, os.path.abspath("src"))

from light_map.camera import Camera
from light_map.calibration_logic import (
    run_calibration_sequence,
    calculate_ppi_from_frame,
    calibrate_extrinsics,
)
from light_map.display_utils import (
    get_screen_resolution,
    setup_logging,
    ProjectorWindow,
    draw_text_with_background,
)
from light_map.core.storage import StorageManager
from light_map.map_config import MapConfigManager


def main():
    parser = argparse.ArgumentParser(description="Projector and Camera Calibration")
    parser.add_argument(
        "--base-dir",
        type=str,
        help="Override base directory for config and data",
        default=None,
    )
    parser.add_argument(
        "--steps",
        nargs="+",
        choices=["projector", "ppi", "extrinsics"],
        default=["projector", "ppi", "extrinsics"],
        help="Calibration steps to run (default: all)",
    )
    args = parser.parse_args()

    storage = StorageManager(base_dir=args.base_dir)
    storage.ensure_dirs()

    setup_logging()
    logger = logging.getLogger(__name__)

    proj_width, proj_height = get_screen_resolution()
    logger.info("Detected Screen Resolution: %dx%d", proj_width, proj_height)

    map_config = MapConfigManager(storage=storage)

    # State variables
    projector_matrix = None
    ppi = map_config.get_ppi()
    ground_points_cam = None
    ground_points_proj = None

    # Try to load existing projector calibration if needed
    calib_file = storage.get_data_path("projector_calibration.npz")
    if os.path.exists(calib_file):
        try:
            data = np.load(calib_file)
            projector_matrix = data["projector_matrix"]
            ground_points_cam = data.get("camera_points")
            ground_points_proj = data.get("projector_points")
            logger.info("Loaded existing projector calibration.")
        except Exception as e:
            logger.warning("Failed to load existing projector calibration: %s", e)

    # Initialize Camera
    logger.info("Initializing Camera...")
    with Camera() as cam:
        for step in args.steps:
            if step == "projector":
                logger.info("--- Step 1: Projector Calibration (Homography) ---")
                result = run_calibration_sequence(
                    cam, projector_width=proj_width, projector_height=proj_height
                )

                if result is not None:
                    projector_matrix, ground_points_cam, ground_points_proj = result
                    logger.info("Saving projector calibration...")
                    np.savez(
                        calib_file,
                        projector_matrix=projector_matrix,
                        camera_points=ground_points_cam,
                        projector_points=ground_points_proj,
                        resolution=np.array([cam.width, cam.height]),
                        camera_resolution=np.array([cam.width, cam.height]),
                        projector_resolution=np.array([proj_width, proj_height]),
                    )
                    logger.info("Projector calibration saved to %s", calib_file)
                else:
                    logger.error("Projector calibration failed.")
                    sys.exit(1)

            elif step == "ppi":
                logger.info("--- Step 2: PPI Calibration ---")
                if projector_matrix is None:
                    logger.error("Projector matrix required for PPI calibration.")
                    continue

                win = ProjectorWindow("ppi_calib", proj_width, proj_height)
                try:
                    instr_frame = np.zeros((proj_height, proj_width, 3), dtype=np.uint8)
                    draw_text_with_background(
                        instr_frame,
                        "PPI Calibration: Place target (100mm, IDs 0 & 1) on table.",
                        (proj_width // 2 - 350, proj_height // 2 - 40),
                        scale=0.8,
                    )
                    draw_text_with_background(
                        instr_frame,
                        "Press Space to Save, Q to Skip.",
                        (proj_width // 2 - 200, proj_height // 2 + 60),
                        scale=0.7,
                    )

                    logger.info(
                        ">>> PPI Calibration: Place target on table. Focus the PROJECTOR WINDOW to press Space/Q."
                    )
                    candidate_ppi = 0.0
                    while True:
                        canvas = instr_frame.copy()
                        frame = cam.read()

                        # Briefly show live camera for alignment if ppi not found
                        if frame is not None and candidate_ppi == 0:
                            # ROI for PPI target is usually central
                            thumb = cv2.resize(frame, (320, 240))
                            canvas[proj_height - 250 : proj_height - 10, 10:330] = thumb
                            draw_text_with_background(
                                canvas, "Camera Feed", (20, proj_height - 20), scale=0.4
                            )

                        if frame is not None:
                            # Re-detect for UI feedback
                            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                            aruco_dict = cv2.aruco.getPredefinedDictionary(
                                cv2.aruco.DICT_4X4_50
                            )
                            parameters = cv2.aruco.DetectorParameters()
                            detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)
                            corners, ids, _ = detector.detectMarkers(gray)

                            ppi_val = calculate_ppi_from_frame(
                                frame,
                                projector_matrix,
                                aruco_corners=corners,
                                aruco_ids=ids,
                            )
                            if ppi_val:
                                candidate_ppi = ppi_val
                                draw_text_with_background(
                                    canvas,
                                    f"Detected PPI: {candidate_ppi:.2f}",
                                    (proj_width // 2 - 150, proj_height // 2 + 120),
                                    color=(0, 255, 0),
                                    scale=1.0,
                                )

                        key = win.update_image(canvas) & 0xFF
                        if key != 255:  # OpenCV 255 = no key
                            logger.debug(
                                f"Captured key: {key} (ord(' ')={ord(' ')}, ord('q')={ord('q')})"
                            )

                        if key == ord(" ") and candidate_ppi > 0:
                            ppi = candidate_ppi
                            map_config.set_ppi(ppi)
                            logger.info("PPI saved: %.2f", ppi)
                            break
                        if key == ord("q"):
                            logger.info("PPI calibration skipped.")
                            break

                        time.sleep(0.01)
                finally:
                    win.close()

            elif step == "extrinsics":
                logger.info("--- Step 3: Camera Extrinsics Calibration ---")
                if projector_matrix is None or ppi <= 0:
                    logger.error(
                        "Projector matrix and PPI required for extrinsics calibration."
                    )
                    continue

                intrinsics_file = storage.get_data_path("camera_calibration.npz")
                if not os.path.exists(intrinsics_file):
                    logger.error("Camera intrinsics (camera_calibration.npz) missing.")
                    continue

                data = np.load(intrinsics_file)
                camera_matrix = data["camera_matrix"]
                dist_coeffs = data["dist_coeffs"]

                # Define 5 Target Zones (Clearly Asymmetric to prevent SolvePnP flip/mirror)
                # w, h are projector resolution
                margin_x, margin_y = 220, 180
                target_zones = [
                    (margin_x + 10, margin_y + 15, "TL"),  # TL (Shifted in+down)
                    (
                        proj_width - margin_x + 60,
                        margin_y - 25,
                        "TR",
                    ),  # TR (Shifted out+up)
                    (
                        margin_x - 50,
                        proj_height - margin_y + 10,
                        "BL",
                    ),  # BL (Shifted out+down)
                    (
                        proj_width - margin_x - 20,
                        proj_height - margin_y - 45,
                        "BR",
                    ),  # BR (Shifted in+up)
                    (
                        proj_width // 2 + 35,
                        proj_height // 2 - 15,
                        "Center",
                    ),  # Center (Off-center)
                ]

                win = ProjectorWindow("extrinsics_calib", proj_width, proj_height)
                try:
                    logger.info(
                        ">>> Extrinsics Arena: Place 3+ tokens. Focus the PROJECTOR WINDOW to press Space/Q."
                    )

                    rvec, tvec = None, None
                    rms_error = 0.0
                    obj_points, img_points = None, None

                    while True:
                        canvas = np.full(
                            (proj_height, proj_width, 3), 200, dtype=np.uint8
                        )
                        frame = cam.read()

                        # Helper camera feed - MOVE TO BOTTOM CENTER
                        if frame is not None:
                            tw, th = 320, 240
                            thumb = cv2.resize(frame, (tw, th))
                            tx_start = (proj_width - tw) // 2
                            ty_start = proj_height - th - 10
                            canvas[
                                ty_start : ty_start + th, tx_start : tx_start + tw
                            ] = thumb
                            draw_text_with_background(
                                canvas,
                                "Camera Feed",
                                (tx_start + 10, ty_start + 25),
                                scale=0.4,
                            )

                        # Detect markers for UI feedback and PnP
                        target_status = ["IDLE"] * len(target_zones)
                        target_info = [{} for _ in range(len(target_zones))]
                        known_targets = {}
                        token_heights = {}

                        if frame is not None:
                            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                            aruco_dict = cv2.aruco.getPredefinedDictionary(
                                cv2.aruco.DICT_4X4_50
                            )
                            detector = cv2.aruco.ArucoDetector(aruco_dict)
                            corners, ids, _ = detector.detectMarkers(gray)

                            if ids is not None:
                                for i, aid in enumerate(ids.flatten()):
                                    # Resolve token properties from tokens.json
                                    resolved = map_config.resolve_token_profile(
                                        int(aid)
                                    )
                                    token_heights[int(aid)] = resolved.height_mm

                                    # Project to screen to match zones
                                    c_cam = np.mean(corners[i][0], axis=0)
                                    pts_cam = np.array(
                                        [c_cam], dtype=np.float32
                                    ).reshape(-1, 1, 2)
                                    pts_proj = cv2.perspectiveTransform(
                                        pts_cam, projector_matrix
                                    ).reshape(-1, 2)
                                    px, py = pts_proj[0]

                                    # Find nearest zone
                                    best_dist = 150.0
                                    best_idx = -1
                                    for idx, (tx, ty, _) in enumerate(target_zones):
                                        dist = math.sqrt(
                                            (px - tx) ** 2 + (py - ty) ** 2
                                        )
                                        if dist < best_dist:
                                            best_dist, best_idx = dist, idx

                                    if best_idx != -1:
                                        target_status[best_idx] = "VALID"
                                        target_info[best_idx] = {
                                            "name": resolved.name,
                                            "height": resolved.height_mm,
                                        }
                                        known_targets[int(aid)] = (
                                            float(target_zones[best_idx][0]),
                                            float(target_zones[best_idx][1]),
                                        )

                            # Solve PnP
                            if len(known_targets) >= 3:
                                result = calibrate_extrinsics(
                                    frame,
                                    projector_matrix,
                                    camera_matrix,
                                    dist_coeffs,
                                    token_heights,
                                    ppi,
                                    ground_points_cam=ground_points_cam,
                                    ground_points_proj=ground_points_proj,
                                    known_targets=known_targets,
                                    aruco_corners=corners,
                                    aruco_ids=ids,
                                )
                                if result:
                                    rvec, tvec, obj_points, img_points = result
                                    # Calculate Reprojection Error
                                    proj_pts_cam, _ = cv2.projectPoints(
                                        obj_points,
                                        rvec,
                                        tvec,
                                        camera_matrix,
                                        dist_coeffs,
                                    )
                                    errors = np.linalg.norm(
                                        img_points - proj_pts_cam.reshape(-1, 2), axis=1
                                    )
                                    rms_error = np.sqrt(np.mean(errors**2))

                        # Draw Target Zones
                        for idx, (tx, ty, label) in enumerate(target_zones):
                            status = target_status[idx]
                            info = target_info[idx]

                            # 2-inch diameter circle (radius = 1 inch = PPI pixels)
                            radius = int(ppi)
                            color = (
                                (0, 255, 0) if status == "VALID" else (255, 255, 255)
                            )

                            if status == "VALID":
                                # Draw DASHED circle boundary to minimize interference
                                from light_map.display_utils import draw_dashed_circle

                                draw_dashed_circle(
                                    canvas,
                                    (tx, ty),
                                    radius,
                                    color,
                                    1,
                                    dash_length_deg=10,
                                )
                                # Faint center crosshair
                                cv2.line(canvas, (tx - 5, ty), (tx + 5, ty), color, 1)
                                cv2.line(canvas, (tx, ty - 5), (tx, ty + 5), color, 1)
                            else:
                                # Draw target cross/rect
                                cv2.rectangle(
                                    canvas,
                                    (tx - 20, ty - 20),
                                    (tx + 20, ty + 20),
                                    color,
                                    1,
                                )
                                cv2.line(canvas, (tx - 30, ty), (tx + 30, ty), color, 1)
                                cv2.line(canvas, (tx, ty - 30), (tx, ty + 30), color, 1)

                            display_label = (
                                info.get("name", label) if status == "VALID" else label
                            )
                            draw_text_with_background(
                                canvas,
                                display_label,
                                (
                                    tx - 40,
                                    ty + radius + 25 if status == "VALID" else ty + 45,
                                ),
                                scale=0.5,
                                color=color if status == "VALID" else (100, 100, 100),
                            )

                        # Draw Reprojection Residuals (Subtle Feedback)
                        if rvec is not None and obj_points is not None:
                            # Use low-contrast color to avoid ArUco interference
                            residual_color = (175, 175, 175)

                            proj_pts_cam_reshaped, _ = cv2.projectPoints(
                                obj_points, rvec, tvec, camera_matrix, dist_coeffs
                            )
                            reprojected_proj = cv2.perspectiveTransform(
                                proj_pts_cam_reshaped, projector_matrix
                            ).reshape(-1, 2)

                            for i in range(len(obj_points)):
                                p_rep = reprojected_proj[i]
                                for idx, (tx, ty, _) in enumerate(target_zones):
                                    if target_status[idx] == "VALID":
                                        # Very thin line and small dot
                                        cv2.line(
                                            canvas,
                                            (int(p_rep[0]), int(p_rep[1])),
                                            (tx, ty),
                                            residual_color,
                                            1,
                                        )
                                        cv2.circle(
                                            canvas,
                                            (int(p_rep[0]), int(p_rep[1])),
                                            2,
                                            residual_color,
                                            -1,
                                        )

                        # HUD
                        valid_count = target_status.count("VALID")
                        instr = (
                            "Space: Accept | Q: Skip"
                            if valid_count >= 3
                            else "Place 3+ tokens on zones"
                        )
                        draw_text_with_background(
                            canvas, instr, (50, proj_height - 50), scale=0.8
                        )

                        if rvec is not None:
                            status_color = (
                                (0, 255, 0)
                                if rms_error < 2.0
                                else (0, 255, 255)
                                if rms_error < 5.0
                                else (0, 0, 255)
                            )
                            draw_text_with_background(
                                canvas,
                                f"Reprojection Error: {rms_error:.2f} px",
                                (proj_width // 2 - 150, 60),
                                color=status_color,
                                scale=0.7,
                            )

                        key = win.update_image(canvas) & 0xFF
                        if key != 255:
                            logger.debug(f"Captured key: {key}")

                        if key == ord(" ") and rvec is not None:
                            ext_file = storage.get_data_path("camera_extrinsics.npz")
                            np.savez(ext_file, rvec=rvec, tvec=tvec)
                            logger.info(
                                "Extrinsics saved to %s (Error: %.2f)",
                                ext_file,
                                rms_error,
                            )
                            break
                        if key == ord("q"):
                            logger.info("Extrinsics calibration skipped.")
                            break

                        time.sleep(0.01)
                finally:
                    win.close()

    logger.info("All selected calibration steps finished.")


if __name__ == "__main__":
    main()
