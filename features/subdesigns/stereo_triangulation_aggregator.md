# Sub-Design Specification: Temporal Matching & 3D Triangulation Aggregator

## 1. Overview & Objectives

This sub-design specifies the 3D stereo triangulation aggregator (`StereoTriangulator` / `TrackingCoordinator`) for `light_map`.

The aggregator runs in the Main Process event loop, consuming asynchronous detection streams from Left and Right detector processes, matching detection pairs using **sliding nearest-neighbor capture timestamps**, computing 3D table-relative coordinates $(X, Y, Z\_{mm})$ via undistorted projection matrix triangulation (`cv2.triangulatePoints`), and executing non-blocking single-camera fallback when occlusions occur.

______________________________________________________________________

## 2. Sliding Nearest-Neighbor Timestamp Matching

```
   Left Queue:   [ D_L(t=100ms) ]  [ D_L(t=133ms) ]  [ D_L(t=166ms) ]
                                          │
                                          │ Nearest Neighbor Match
                                          │ |133 - 138| = 5ms <= Delta_t_match
                                          ▼
   Right Queue:  [ D_R(t=104ms) ]  [ D_R(t=138ms) ]  [ D_R(t=172ms) ]
```

### 2.1 Non-Genlocked Camera Clock Matching Policy

Because Raspberry Pi Camera Module 3 sensors run on independent free-running clocks without hardware genlock, frame capture times drift naturally within the camera's frame period ($\\bar{T}\_{\\text{frame}}$):

1. **Inbound Result Ring Buffer:** The aggregator maintains a short sliding buffer (covering up to 2–3 frame periods) of detection results for Left and Right streams.
1. **Nearest-Neighbor Search:** For an unmatched Left result $D_L(t_L)$, the aggregator searches the Right buffer for a result $D_R(t_R)$ minimizing $|t_L - t_R|$.
1. **Adaptive Acceptance Threshold ($\\Delta t\_{match}$):**
   - To prevent a single frame from Camera Left matching two sequential frames from Camera Right, the matching threshold is capped strictly below $0.5 \\times \\bar{T}_{\\text{frame}}$:
     $$\\Delta t_{\\text{match}} = \\min\\left(0.4 \\times \\bar{T}\_{\\text{frame}},; \\text{max_allowed_skew}\\right)$$
   - **Ingestion-Driven Fallback Timeout ($T\_{timeout}$):** Fallback is triggered when a newer frame $N+2$ is ingested from one camera while frame $N$ remains missing from the other camera, avoiding false fallbacks caused by OS scheduling delays.

______________________________________________________________________

## 3. 3D Stereo Triangulation Engine

### 3.1 2D Point Undistortion & ROI Reconstruction

Before triangulation, raw 2D centroids in cropped sensor space are converted to undistorted normalized image points:

1. **ROI Offset Addition:**
   $$u_L = u\_{\\text{crop},L} + \\text{roi_offset_x}_L, \\quad v_L = v_{\\text{crop},L} + \\text{roi_offset_y}_L$$
   $$u_R = u_{\\text{crop},R} + \\text{roi_offset_x}_R, \\quad v_R = v_{\\text{crop},R} + \\text{roi_offset_y}\_R$$
1. **Lens Undistortion:**
   ```python
   pts_L_undist = cv2.undistortPoints(np.array([[u_L, v_L]], dtype=np.float32), K_L, dist_L, P=K_L)
   pts_R_undist = cv2.undistortPoints(np.array([[u_R, v_R]], dtype=np.float32), K_R, dist_R, P=K_R)
   ```

### 3.2 Projection Matrix Triangulation (`cv2.triangulatePoints`)

Using calibrated table extrinsics $(R_L, t_L)$, $(R_R, t_R)$ and undistorted camera projection matrices:

$$P_L = K_L \\begin{bmatrix} R_L \\mid t_L \\end{bmatrix}, \\quad P_R = K_R \\begin{bmatrix} R_R \\mid t_R \\end{bmatrix}$$

```python
pts_4d = cv2.triangulatePoints(P_L, P_R, pts_L_undist, pts_R_undist)
X = pts_4d[0] / pts_4d[3]
Y = pts_4d[1] / pts_4d[3]
Z_mm = pts_4d[2] / pts_4d[3]
```

### 3.3 Reprojection Error Filtering

To reject noisy detections or false positive pairs:

- Calculate 2D reprojection error by projecting $(X, Y, Z\_{mm})$ back onto Camera Left and Right image planes.
- Reject points with reprojection error $> 3.0\\text{ pixels}$.

______________________________________________________________________

## 4. Single-Camera Occlusion Fallback Logic

When an object or hand is blocked from one camera's line-of-sight, the aggregator executes single-camera fallback to prevent tracking loss or visual flickering.

### 4.1 Token Fallback ($Z = h\_{token}$)

- **World Ray Transformation:**
  1. Retrieve token height $h\_{token}$ from `tokens.json` (`aruco_defaults` / `token_profiles`).
  1. Compute normalized ray direction in camera space $\\mathbf{d}\_{cam} = K_L^{-1} (u_L, v_L, 1)^T$.
  1. Transform ray to World Table coordinates: $\\mathbf{d}_{world} = R_L^T \\mathbf{d}_{cam}$.
  1. Intersect ray with plane $Z = h\_{token}$:
     $$s = \\frac{h\_{token} - C\_{L,z}}{d\_{world,z}}$$
     $$\\mathbf{P}\_{table} = \\mathbf{C}_L + s \\cdot \\mathbf{d}_{world}$$
  1. Yields accurate base tabletop position $(X, Y)$ without parallax distortion.

### 4.2 Hand / Fingertip Fallback ($Z = Z\_{last_known}$)

- Intersects single-camera ray with plane $Z = Z\_{last_known}$ (the last successfully triangulated hand elevation).
- If no prior 3D hand elevation exists, defaults to tabletop plane $Z=0\\text{mm}$.

______________________________________________________________________

## 5. Verification Criteria

- [ ] Nearest-neighbor matching window threshold strictly $< 0.5 \\times \\bar{T}\_{\\text{frame}}$ prevents 1-to-many frame matching errors.
- [ ] 2D centroids are reconstructed ($u\_{\\text{full}} = u\_{\\text{crop}} + \\text{roi_offset_x}$) and undistorted via `cv2.undistortPoints` before triangulation.
- [ ] `cv2.triangulatePoints` output for known 50mm tokens yields $Z\_{mm} = 50.0 \\pm 2.0\\text{mm}$.
- [ ] Reprojection error filter rejects mismatched pairs exceeding 3.0 pixels error.
- [ ] Single-camera ray fallback transforms direction vector $\\mathbf{d}_{world} = R_L^T \\mathbf{d}_{cam}$ before intersecting $Z = h\_{token}$.
