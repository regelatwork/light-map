# Design: 3D Projector Pose Calibration (Intrinsics & Extrinsics)

## 1. Overview
The current Light Map system utilizes a 2D Homography ($H$) to map camera pixels to projector pixels. While effective for the $Z=0$ tabletop surface, this model fails to account for the projector's perspective shift (parallax) when projecting onto objects of height $Z > 0$. 

This design transitions the projector to a full **3D Projection Model**, treating it as an "inverse camera" with its own intrinsic matrix ($K_p$) and extrinsic pose ($R_p, t_p$).

## 2. Goals
- **Parallax-Corrected Projection**: Accurately align digital overlays (e.g., status icons, vision masks) with the tops of physical tokens.
- **Robust 3D Mapping**: Move from a planar mapping to a volumetric mapping of the interaction space.
- **User-Friendly Calibration**: Minimize manual effort using automated ArUco projection and gesture-based triggers.
- **System-Wide Consistency**: Replace scattered 2D homography calls with a centralized 3D projection API.

## 3. Data Structures

### 3.1 `AppConfig` Updates (System Settings)
Added to `src/light_map/map_config.py` (or global system settings):
- `calibration_box_height_mm` (float): Height of the physical calibration target (Default: 78.0).
- `use_projector_3d_model` (bool): Master toggle to enable 3D projection (Default: False).

### 3.2 `projector_3d_calibration.npz`
Stored in the user data directory:
- `mtx` (3x3 float): Projector Intrinsic Matrix.
- `dist` (1x5 or 1x8 float): Projector Distortion Coefficients.
- `rvec` (3x1 float): Projector Rotation Vector (World to Projector).
- `tvec` (3x1 float): Projector Translation Vector (World to Projector).
- `rms` (float): Root Mean Square error of the calibration.

## 4. Physical Calibration Target
A single box of known dimensions ($78 \times 188 \times 295$ mm) serves as a portable $Z$-plane.

## 5. Calibration Workflow (`Projector3DCalibrationScene`)
1. **Interactive Placement**: Projector highlights a "Target Zone"; user places the box.
2. **Multi-Marker Projection**: Projects a $3 \times 2$ ArUco grid on the box ($Z=H$) and reference markers on the table ($Z=0$).
3. **Gesture-Triggered Capture**: User performs the **Victory** gesture to sample points.
4. **3D Reconstruction**: Camera rays are intersected with $Z=H$ or $Z=0$ planes to find World Coordinates $(X, Y, Z)_w$.
5. **Solver**: Uses `cv2.calibrateCamera` to calculate $K_p, D_p, R_p, t_p$.

## 6. Centralized Projection API
To prevent fragmented logic, a new `Projector3DModel` class will be created in `src/light_map/vision/projector.py`.

```python
class Projector3DModel:
    def project_world_to_projector(self, points_3d: np.ndarray) -> np.ndarray:
        """
        Maps (N, 3) World points to (N, 2) Projector pixels.
        If use_projector_3d_model is False, falls back to 2D Homography (assuming Z=0).
        """
        if self.use_3d:
            # Full 3D Projective transformation
            pts_p, _ = cv2.projectPoints(points_3d, self.rvec, self.tvec, self.mtx, self.dist)
            return pts_p.reshape(-1, 2)
        else:
            # Fallback to 2D Homography (ignoring Z height)
            return cv2.perspectiveTransform(points_3d[:, :2], self.H)
```

## 7. Migration Scope (Code Changes)

### 7.1 Component Updates
All components currently using `cv2.perspectiveTransform` for projector mapping must be updated to use the `Projector3DModel` API:
- **`ArucoMaskLayer`**: Map marker corners at their detected height $h$ to projector space.
- **`HandMaskLayer`**: Map hand positions to projector coordinates (assuming hand height or $Z=0$).
- **`FlashDetector`**: Use the 3D model to calculate expected dot positions at variable surface heights.
- **`InputProcessor`**: Ensure UI interactions (gestures) at height $Z$ are mapped correctly to projector coordinates.

### 7.2 Interface Changes
- `Renderer` and `Scene` contexts will now hold an instance of `Projector3DModel`.
- `ArucoMaskLayer.config` will lose `parallax_factor` in favor of the automated 3D model.

## 8. Testing Details

### 8.1 Automated Unit Tests
- **Solver Verification**: Test `calibrate_projector_3d` with synthetic 3D-to-2D correspondences and verify it recovers known pose/intrinsics.
- **Fallback Logic**: Verify `Projector3DModel` correctly falls back to Homography when 3D data is absent or disabled.
- **Numerical Consistency**: Verify that `project_world_to_projector(X, Y, 0)` with the 3D model yields results similar to the 2D Homography for planar points.

### 8.2 Integration & Manual Tests
- **Wireframe Alignment**: Project a virtual box and verify it aligns with the physical box at multiple positions.
- **Parallax Stress Test**: Place a tall token on the table and verify the mask stays centered as the token moves across the field of view.

## 9. Success Criteria
- **Reprojection Error**: RMS error $< 2.0$ pixels.
- **Zero Drift**: No visible "sliding" of overlays when height $Z$ changes.
