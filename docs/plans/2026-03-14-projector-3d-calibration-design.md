# Design: 3D Projector Pose Calibration (Intrinsics & Extrinsics)

## 1. Overview
The current Light Map system utilizes a 2D Homography ($H$) to map camera pixels to projector pixels. While effective for the $Z=0$ tabletop surface, this model fails to account for the projector's perspective shift (parallax) when projecting onto objects of height $Z > 0$. 

This design transitions the projector to a full **3D Projection Model**, treating it as an "inverse camera" with its own intrinsic matrix ($K_p$) and extrinsic pose ($R_p, t_p$).

## 2. Goals
- **Parallax-Corrected Projection**: Accurately align digital overlays (e.g., status icons, vision masks) with the tops of physical tokens.
- **Robust 3D Mapping**: Move from a planar mapping to a volumetric mapping of the interaction space.
- **User-Friendly Calibration**: Minimize manual effort using automated ArUco projection and gesture-based triggers.
- **Precision Masking**: Eliminate the need for heuristic "parallax factor" sliders in ArUco masking.

## 3. Physical Calibration Target
The system will use a single "Calibration Box" with known dimensions:
- **Height**: 78 mm (User-configurable)
- **Width**: 188 mm
- **Length**: 295 mm

The box serves as a portable $Z$-plane, allowing the system to capture 3D-to-2D correspondences at both $Z=0$ (table) and $Z=H$ (box top).

## 4. Calibration Workflow (`Projector3DCalibrationScene`)
1. **Setup**: The user enters the 3D Projector Calibration scene. The system retrieves box dimensions from `SystemConfig`.
2. **Interactive Placement**:
   - The projector highlights a "Target Zone" on the table.
   - The user places the box in the zone.
3. **Multi-Marker Projection**:
   - The projector displays a $3 \times 2$ grid of ArUco markers on the top surface of the box ($Z=78$).
   - Simultaneously, it projects reference ArUco markers on the surrounding tabletop ($Z=0$).
4. **Gesture-Triggered Capture**:
   - The user steps back and performs the **Victory** gesture.
   - The camera captures a frame and detects all ArUco corners.
5. **3D Reconstruction**:
   - For each detected corner $(u_c, v_c)$ in the camera image:
     - The system projects a ray from the camera center through the pixel.
     - The ray is intersected with the plane $Z=H$ (for box markers) or $Z=0$ (for table markers) using the **Camera's 3D Extrinsics**.
     - This yields a precise World Coordinate $(X, Y, Z)_w$.
6. **Repetition**: The process is repeated for 4–6 different box locations to ensure coverage of the entire projection volume.

## 5. Mathematical Solver
- **Correspondence Set**: A collection of pairs: `(Projector Pixel (u_p, v_p), World Coordinate (X, Y, Z)_w)`.
- **Algorithm**: OpenCV `cv2.calibrateCamera` is used, treating the projector as a camera and the $(X, Y, Z)_w$ points as the "object points."
- **Outputs**:
  - `K_p`: Projector Intrinsic Matrix (Focal length, principal point).
  - `D_p`: Projector Distortion Coefficients.
  - `R_p, t_p`: Projector 3D Pose relative to the World $(0,0,0)$ origin.

## 6. Impact on ArUco Masking and Tracking

### 6.1 Elimination of Heuristics
The current `parallax_factor` slider in `ArucoMaskLayer` is a heuristic used to "guess" the projector's perspective shift by sliding 2D camera coordinates. With a 3D projector model, this shift is mathematically exact.

- **Current Logic**: `target_pix = camera_pix + shift * parallax_factor`.
- **New Logic**: `target_pix = Project(World_Point_3D)`.

### 6.2 Precision Masking for Tall Tokens
For a token of height $h$, we already calculate its world coordinates $(X, Y, h)_w$ using the camera's pose. 
- The system will project these **3D coordinates** directly through the **Projector's 3D Matrix**.
- This ensures the "blackout mask" perfectly matches the physical footprint of the token as seen from the projector's specific 3D viewpoint.

## 7. Code Migration Plan

### 7.1 `src/light_map/aruco_mask_layer.py`
- **Remove**: The `parallax_factor` and the camera-space shift logic in `_project_to_projector`.
- **Implement**: A new projection method that uses the stored `projector_3d_pose.npz` (intrinsics + extrinsics).
- **Update**: `_generate_patches` to pass the token's 3D corners $(X, Y, h)$ directly to the new 3D projection function.

### 7.2 `src/light_map/calibration_logic.py`
- **New Function**: `calibrate_projector_3d(correspondences)`:
  - Takes the list of `(u_p, v_p) -> (X, Y, Z)_w`.
  - Performs `cv2.calibrateCamera`.
  - Returns `K_p, D_p, rvec_p, tvec_p`.

### 7.3 `src/light_map/renderer.py`
- **Update**: The base projection logic should prioritize the 3D Projector Model if available, falling back to 2D Homography only if 3D calibration is missing.

## 8. Success Criteria & Validation
- **Reprojection Error**: The average distance between detected corners and projected corners should be $< 2.0$ pixels.
- **Physical Alignment**: A projected wireframe box must align with the physical edges of the 78mm box regardless of its position on the table.
- **Parallax Stability**: A status icon projected "on top" of a token should not appear to "slide" off the token when the token is moved across the table.
