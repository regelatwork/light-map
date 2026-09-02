# Sub-Design Specification: Unified Stereo Calibration & Auto-Discovery Wizard

## 1. Overview & Goals

This sub-design specifies the unified calibration procedure and auto-discovery system for the dual-camera stereographic vision architecture in `light_map`.

The calibration process solves essential spatial parameters in a **structured, single-sweep scene**:

1. **Camera Lens Intrinsics ($K_L, dist_L$ and $K_R, dist_R$):** Loaded from pre-calibrated lens profiles (with fallback order).
1. **Stereo Baseline & Relative Transform ($[R\_{stereo} \\mid T\_{stereo}]$):** Calculates the exact 3D offset between Camera Left and Camera Right (nominal 128mm separation).
1. **Auto-Role Identification (Left vs Right):** Discovers physical camera assignments (`/dev/video0` vs `/dev/video1`) automatically using relative horizontal displacement $+T_x$ and verifies rotation alignment $R\_{stereo}$.
1. **Table Surface ($Z=0$) & Projector Homography:** Aligns tabletop space with projector pixels.
1. **Physical Scale (PPI) & 3D Height Scale ($Z\_{mm}$):** Calculates physical tabletop PPI and verifies non-planar $Z>0$ extrusion accuracy.

______________________________________________________________________

## 2. ArUco Marker ID Space Partitioning

To maintain optimal camera detection speed and resolution readability, `light_map` retains `cv2.aruco.DICT_4X4_50` (50 unique IDs: `0` through `49`) and partitions the ID space:

| Range | Purpose | Description |
| :--- | :--- | :--- |
| **`0` – `39`** | User Game Tokens | Physical gaming tokens placed on PCs, NPCs, and terrain objects. |
| **`40` – `41`** | Physical PPI Ruler Sheet | Printed target sheet containing 2 ArUco markers (IDs 40 & 41) separated by a known physical distance ($d = 100\\text{mm}$). |
| **`42` – `49`** | Projected Calibration Arena | ArUco markers projected by the system onto the $Z=0$ table surface during calibration. |

______________________________________________________________________

## 3. Calibration Token Configuration & Height Lookup

- **Dynamic Height Resolution:** During calibration, the wizard selects candidate PC tokens from `tokens.json` (e.g. IDs 0, 1, 2, 3: *Cricket*, *Lace*, *Shikra*, *Verita*).
- **Token Validation:** The wizard explicitly filters `tokens.json` to only select candidate tokens with resolved, positive heights ($h\_{mm} > 0$), resolving profile references (e.g. `profile: "pc"` $\\to 50.0\\text{mm}$).
- **Pre-Calibrated Lens Intrinsics & Fallback Resolution:**
  To ensure backwards compatibility with single-camera systems and identical lens hardware, intrinsics ($K, dist$) are resolved in the following fallback order:
  - **Camera Left:** Looks for `camera_left_calibration.npz` $\\to$ falls back to `camera_calibration.npz`.
  - **Camera Right:** Looks for `camera_right_calibration.npz` $\\to$ falls back to `camera_calibration.npz`.
  - If both cameras share the same model (e.g. RPi Cam 3), `camera_calibration.npz` serves as the shared single-file default for both streams.

______________________________________________________________________

## 4. Single-Sweep Calibration Scene & Sequential Solver

```
+-------------------------------------------------------------------------+
|                              PROJECTOR DISPLAY                          |
|                                                                         |
|  [Target 1: Top-Left]                           [Target 2: Top-Right]   |
|  (Place Token 1 - 50mm)                        (Place Token 10 - 50mm) |
|          O                                                 O            |
|                                                                         |
|                       +------------------------+                        |
|                       | Projected ArUco Grid   |                        |
|                       | (IDs 42-47, Z=0)       |                        |
|                       +------------------------+                        |
|                                                                         |
|                                [Physical PPI Sheet]                     |
|                                (IDs 40-41, Z=0)                        |
|                                                                         |
|  [Target 3: Bottom-Left]                        [Target 4: Bottom-Right]|
|  (Place Token 20 - 50mm)                       (Place Token 30 - 50mm) |
|          O                                                 O            |
+-------------------------------------------------------------------------+
```

### 4.1 Sequential Solver Sequence

To avoid solving disjoint points with unscaled physical geometry:

1. **Phase 1: Table Scale & $Z=0$ Homography:**
   - Detect projected grid (IDs 42–47) and physical PPI sheet (IDs 40 & 41, $d=100\\text{mm}$) simultaneously.
   - Calculate physical PPI (`projector_ppi`) and map projected marker corners to physical millimeter tabletop coordinates $(X, Y, Z=0)$.
1. **Phase 2: Joint Non-Planar Stereo Extrinsics Solve:**
   - Detect 4 elevated PC tokens (IDs 0, 1, 2, 3) placed on projected corner target rings, fetching their heights ($Z=h$) from `tokens.json`.
   - Combine scaled $Z=0$ tabletop grid points and $Z=h$ token points into `cv2.stereoCalibrate` and `cv2.solvePnP` to resolve rigid extrinsics $(R_L, t_L)$ and $(R_R, t_R)$ without planar ambiguity.
1. **Phase 3: Auto-Discovery & Orientation Verification:**
   - Compute relative translation vector $T\_{stereo}$ and rotation matrix $R\_{stereo}$.
   - Camera observing positive $+T_x$ horizontal displacement is assigned `camera_right`.
   - Verify relative rotation angle $< 10^\\circ$ to confirm cameras are mounted in the same physical orientation.

### 4.2 Two-Pass Auto-Calculated Sensor ROI (200mm Parallax Margin)

1. **Pass 1 (Uncalibrated Bounds):** Calibration begins with full-frame uncropped sensor capture to detect projected table viewport boundary on the image plane, establishing safe initial crop limits.
1. **Pass 2 (3D Parallax Volume Envelope):**
   - Using solved extrinsics $(R, t)$, project the 4 viewport corners at both tabletop level ($Z=0\\text{mm}$) and maximum object height ($Z=200\\text{mm}$).
   - Sensor ROI is computed as the 2D bounding envelope containing both $Z=0$ and $Z=200\\text{mm}$ projections plus a 5% safety margin.
   - Saved as `roi_left` and `roi_right` in `stereo_calibration.json`.

______________________________________________________________________

## 5. Script Updates & Tooling

1. **`scripts/generate_calibration_target.py` Update:**
   - Update script to use `cv2.aruco.DICT_4X4_50` and IDs **`40`** & **`41`** (replacing legacy IDs 0 & 1).
   - Include clear printed text label: `"Light Map Physical PPI Calibration Ruler (IDs 40 & 41, Distance: 100mm)"`.
1. **`tokens.json` Scrub:**
   - Ensure user tokens occupy IDs `0–39` strictly, removing legacy ID `"42"`.

______________________________________________________________________

## 6. Verification Criteria

- [ ] `generate_calibration_target.py` produces an SVG with IDs **40 & 41** using `DICT_4X4_50`.
- [ ] Wizard filters `tokens.json` to only select candidate tokens with resolved, positive height ($h\_{mm} > 0$).
- [ ] Stereo calibration wizard successfully identifies Left vs Right cameras based on $+T_x$ displacement and relative rotation matrix $R\_{stereo}$.
- [ ] Sequential solver computes PPI first, then non-planar stereo extrinsics using scaled $Z=0$ and $Z=h$ points.
- [ ] Two-pass ROI calculation computes `roi_left` and `roi_right` incorporating $Z=200\\text{mm}$ vertical margin.
- [ ] Triangulated 3D position of an ArUco marker matches physical measurement within $\\pm 2.0\\text{mm}$ error across tabletop area.
