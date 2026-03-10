# Calibration Guide

This guide provides comprehensive instructions for calibrating the Light Map system, ensuring precise alignment between the physical tabletop and digital projections.

______________________________________________________________________

## 1. Hardware Setup & Best Practices

For reliable tracking and projection, your hardware environment must be stable.

### Web Calibration Wizards

As a user-friendly alternative to gesture-based menus or command-line scripts, you can use the **Light Map Control Dashboard** (available at `http://localhost:8000`) while the app is running. It provides a guided interface for all calibration routines described below, including a real-time camera preview.

### Stability

- **Tripod/Mount**: The camera and projector MUST be securely mounted. Any movement after calibration will invalidate the results.
- **Surface**: The tabletop should be flat and vibration-free.

### Lighting

- **Ambient Light**: Avoid direct sunlight or strong glare on the tabletop, as this can interfere with ArUco marker detection.
- **Projector Brightness**: Ensure the projector is bright enough to be clearly seen by the camera, but not so bright that it saturates the camera sensor.

### Camera Focus

- Focus the camera on the tabletop surface. If using a lens with a shallow depth of field, ensure the entire interaction area is reasonably sharp.

______________________________________________________________________

## 2. Camera Intrinsics Calibration

Camera intrinsics define the internal characteristics of the camera (focal length, optical center, and lens distortion).

### Why it's needed

Standard camera lenses (especially wide-angle) have barrel or pincushion distortion. Calibrating intrinsics allows the system to "undistort" the image, which is critical for accurate 3D pose estimation (`solvePnP`).

### Usage

1. **Prepare Target**: Use a standard 13x18 (or similar) chessboard pattern.
1. **Launch Scene**: Open the menu and select **Calibration > 1. Camera Intrinsics**.
1. **Capture Images**: Hold the chessboard in front of the camera in various positions and orientations. Use the **Closed Fist** gesture to capture a frame. Capture at least 15-20 images for good results.
1. **Process**: The system will automatically compute the camera matrix and distortion coefficients and save them to `camera_calibration.npz`.

______________________________________________________________________

## 3. Projector-Camera (Sequential) Calibration

This step maps camera pixels directly to projector pixels and can sequentially calibrate PPI and Camera Extrinsics.

### Usage

1. Ensure `camera_calibration.npz` exists (see Step 2).
1. Run the standalone calibration utility:
   ```bash
   python scripts/projector_calibration.py
   ```
1. **Sequential Steps**: By default, the script runs three calibrations one after the other:
   - **Step 1: Projector Homography**: The system projects a fullscreen checkerboard. Ensure the camera sees the entire pattern.
   - **Step 2: Physical PPI**: Place the 100mm ArUco target (IDs 0 & 1). A live preview helps with alignment. **Press Space to Save**.
   - **Step 3: Camera Extrinsics**: Enter the **Calibration Arena**. Place 3+ known tokens on the asymmetric target zones (TL, TR, BL, BR, Center).
1. **Calibration Arena UI**:
   - **Target Zones**: Turn green when a valid token is detected.
   - **Reprojection Residuals**: Subtle gray lines show the error between detection and the mathematical model.
   - **Validation**: Real-time RMS error is displayed (aim for < 2.0px).
   - **Controls**: **Space** to Accept/Save, **Q** to Skip.
1. **Overrides**: Use the `--steps` argument to run specific calibrations:
   ```bash
   python scripts/projector_calibration.py --steps projector ppi
   ```

The resulting matrices and raw calibration points are saved to `projector_calibration.npz`, PPI is saved to the global configuration, and pose data is saved to `camera_extrinsics.npz`.

______________________________________________________________________

## 4. PPI Calibration (Pixels Per Inch)

PPI calibration tells the system how many projector pixels represent one physical inch on the table. This is required for 1:1 map scaling.

### Usage

1. **Print Target**: Run `python scripts/generate_calibration_target.py` and print the resulting `calibration_target.svg` at 100% scale.
1. **Place Markers**: Place the printed target on the table. It contains two ArUco markers (IDs 0 and 1) exactly 100mm apart.
1. **Detect**: Select **Calibration > 3. Physical PPI** (or **Map Settings > Calibrate PPI**). The system will detect the markers and calculate the PPI.
1. **Confirm**: A 1-inch grid will be projected. Verify its accuracy and use the **Victory** gesture to save.

______________________________________________________________________

## 5. Camera Extrinsics (Pose Estimation)

Extrinsics define the camera's 3D position ($t$) and orientation ($R$) relative to the tabletop.

### Theory: Parallax and solvePnP

Because the camera is offset from the projector's optical axis, objects with height (tokens) appear shifted compared to the flat map. This is **Parallax Error**.
To correct this, we use `cv2.solvePnP` to find the camera's pose. By knowing the camera's 3D position, the system can use **Ray-Plane Intersection** to find the true base $(X, Y)$ of a token given its detected top-marker position and known height $h$.

### Usage

1. **Prepare Tokens**: Use at least 3-5 tokens with known ArUco IDs (configured in `global_settings.aruco_defaults`).
1. **Placement**: Select **Calibration > 4. Camera Extrinsics**. Place tokens on the projected target zones.
1. **Validation**: The system will show a **Validation HUD** with the RMS Reprojection Error.
   - **Green (< 2.0px)**: Excellent.
   - **Yellow (2.0 - 5.0px)**: Acceptable.
   - **Red (> 5.0px)**: Poor. Check lighting or marker height config.
1. **Save**: Use the **Victory** gesture to save the pose to `camera_extrinsics.npz`.

______________________________________________________________________

## 6. Map Grid Calibration

Aligns a digital map's grid with the physical 1-inch tabletop grid.

### Usage

1. Load a map and select **Map Settings > Set Scale** (or **Maps > [Map Name] > Calibrate Scale**).
1. A 1-inch grid with crosshairs will be projected.
1. Use **Pan** (Fist) and **Zoom** (Two-Hand Pointing) gestures to align the map's grid lines with the projected crosses.
1. **Victory** to save the alignment for that specific map.

______________________________________________________________________

## Troubleshooting

| Issue | Potential Cause | Solution |
| :--- | :--- | :--- |
| **Marker not detected** | Poor lighting or glare | Adjust ambient light; use matte markers. |
| **High Reprojection Error** | Incorrect token height | Verify `height_mm` in the global configuration. |
| **Edges are misaligned** | Lens distortion | Ensure Camera Intrinsics are accurate; use `visualize_distortion.py`. |
| **Calibration drift** | Camera/Projector moved | Re-calibrate. Use rigid mounts to prevent movement. |
| **"Homography failed"** | Pattern too small | Ensure the projector pattern fills most of the camera's view. |

______________________________________________________________________

## Math for Maintainers

### Parallax Correction

Given a camera coordinate $p = [u, v, 1]^T$, the ray in world space is:
$$R(s) = C + s \\cdot (R^T \\cdot K^{-1} \\cdot p)$$
where $C$ is the camera center, $R$ is the rotation matrix, and $K$ is the intrinsic matrix. We solve for $s$ such that the Z-coordinate of $R(s)$ equals the token height $h$.

### Non-Linear Residuals

While homography handles perspective, it doesn't account for radial lens distortion in the projector. The `ProjectorDistortionModel` stores a grid of residuals $(dx, dy)$ measured during calibration and applies them as a secondary correction after the linear homography.
