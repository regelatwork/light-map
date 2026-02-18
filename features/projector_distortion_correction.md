# Projector Distortion Correction

## 1. Goal

To implement a non-linear correction system that compensates for lens distortion (barrel/pincushion) and keystone effects in the projector-camera system. This ensures that projected UI elements and detected token coordinates align perfectly with the map, especially at the edges of the projection area where homography-only models fail.

## 2. Problem: Non-Linear Distortion

Standard **Homography** (a 3x3 matrix) is a linear transformation that can only account for rotation, scale, translation, and perspective (keystoning) on a flat plane. It assumes the lens is perfect (pinhole model).

However, many short-throw projectors (common in tabletop RPG setups) exhibit significant **Barrel Distortion**, where the image "bulges" outward. This causes:

- Menu buttons at the edges to be 10-20px away from the hand's projected position.
- Tokens at the edges to be detected in the wrong grid cell.
- Straight lines in the SVG appearing curved on the map.

## 3. Solution: Residual Field Correction

Instead of a complex radial distortion model (like OpenCV's `distCoeffs`), which is hard to calibrate for a projector without special hardware, we use a **Grid-Based Residual Model**.

### 3.1 Calibration Data

The calibration process captures a grid of points:

- $C\_{cam}$: Detected chessboard corners in Camera Space.
- $P\_{true}$: Known target coordinates in Projector (Screen) Space.

### 3.2 Residual Calculation

1. Compute the linear homography $H$ from $C\_{cam} \\to P\_{true}$.
1. For each calibration point, calculate the **Theoretical Point**: $P\_{theo} = H \\cdot C\_{cam}$.
1. Calculate the **Residual** (Error): $R = P\_{true} - P\_{theo}$.
1. Store these $(dx, dy)$ residuals as a displacement field indexed by the projector coordinates.

### 3.3 Non-Linear Mapping (Bilinear Interpolation)

To map any camera point $p\_{cam}$ to a corrected projector point $p\_{proj}$:

1. Apply the linear homography: $p\_{raw} = H \\cdot p\_{cam}$.
1. Locate $p\_{raw}$ within the calibration grid cells.
1. Perform **Bilinear Interpolation** of the residuals at the four nearest grid corners to find the specific error $r\_{interp}$ for that coordinate.
1. Correct the point: $p\_{proj} = p\_{raw} + r\_{interp}$.

## 4. Implementation Details

- **`ProjectorDistortionModel` (`src/light_map/projector.py`)**:
  - Stores the homography and the residual grid.
  - `apply_correction(points_cam)`: Full pipeline for camera-to-screen mapping.
  - `correct_theoretical_point(px, py)`: Refines points already in screen space (e.g., from unwarped frames).
- **`TokenTracker`**: Utilizes `correct_theoretical_point` to refine centroids extracted from warped flash frames and `apply_correction` for structured light centroids.
- **`InteractiveApp`**: Injects the model into the input pipeline to correct hand landmarks.
- **`visualize_distortion.py`**: Diagnostics script to plot the vector field of residuals, helping verify calibration quality.

## 5. Rationale

- **No Dependencies**: Avoids `scipy.interpolate` (not in project requirements), using a lightweight custom bilinear solver.
- **Generic**: Corrects *any* non-linear distortion (barrel, keystone, or even minor lens imperfections) without needing a specific mathematical lens model.
- **Performance**: $O(1)$ lookup for interpolation is extremely fast and scalable for real-time tracking.
- **Robustness**: Clamps to edge residuals for points outside the calibration grid, providing a graceful fallback.

## 6. Testing Strategy

- **`visualize_distortion.py`**: Visual confirmation that vectors are small and follow a radial pattern (center to edge).
- **Radial Correlation Diagnostic**: `TokenTracker` debug mode now reports mean error in three zones (Center, Mid, Edge). Successful correction should see these values drop to < 2px across the entire screen.
