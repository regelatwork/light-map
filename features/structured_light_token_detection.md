# Structured Light Token Detection

## 1. Goal

To implement a robust token detection algorithm that leverages structured light (specifically **Dot Grid Disparity**) to distinguish physical tokens from the flat map surface. This provides an alternative to the current contrast-based "Flash" method, which can fail when token colors match the map background.

## 2. Core Concept: Dot Grid Disparity

The algorithm relies on the geometric relationship between the camera and the projector. Since they are at different physical positions, objects with height (tokens) will cause a parallax shift in the observed position of projected patterns compared to the flat surface (map).

### Validated Logic

- **Existing Homography**: The `projector_matrix` ($H$) transforms points from **Camera Space** $\\to$ **Projector Space**.
- **Non-Linear Correction**: To account for lens distortion (barrel/keystone), the system optionally applies a `ProjectorDistortionModel` ($f(x)$) which interpolates residuals from a calibration grid: $P = f(H \cdot P_{cam})$.
- **Planar Assumption**: The calibration assumes the map is a flat plane. Any deviation in height ($z > 0$) results in a coordinate shift when viewed from the camera's offset angle.
- **Mechanism**:
  1. Project a grid of dots at known projector coordinates $P\_{expected}$.
  1. Camera observes dots at $P\_{cam}$.
  1. Transform observed points: $P'_{proj} = H \\cdot P_{cam}$.
  1. **Disparity**: On the flat calibrated surface, $P'_{proj} \\approx P_{expected}$. If a token is present, the height $h$ causes a shift, so $||P'_{proj} - P_{expected}|| > \\text{threshold}$.

## 3. Detailed Technical Specifications

### 3.1 Pattern Generation (`get_scan_pattern`)

The tracker generates a **Jittered Grid**. This combines the uniform coverage of a grid with the non-periodicity of random noise, preventing "aliasing" (ghosting) where shifted dots land on neighbors.

- **Parameters**: `width`, `height`, `ppi`.
- **Spacing**: `spacing = max(20, int(ppi * 0.4))`.
- **Jitter**: `max_jitter = spacing // 2 - 2`.
- **Algorithm**:
  1. Create black image.
  1. Iterate grid positions `(gx, gy)`.
  1. Add random offset: `x = gx + randint(-max_jitter, max_jitter)`, `y = gy + randint(-max_jitter, max_jitter)`.
  1. Store `expected_points` (Projector Space).
  1. Draw dots.

### 3.2 Detection Pipeline (Camera Frame)

1. **Capture & Difference**:
   - Capture `Frame_Dark` and `Frame_Pattern`.
   - `diff = Frame_Pattern - Frame_Dark`.
   - Threshold to find white dots.
1. **Centroid Extraction**:
   - Get centroids of all blobs: `observed_points_cam` (Camera Space).
1. **Transform**:
   - Convert `observed_points_cam` $\\to$ `observed_points_proj` using `projector_matrix` and the `ProjectorDistortionModel` (if available).

### 3.3 Token Identification (Occlusion + Disparity)

Instead of relying solely on missing floor points, we combine two signals for robustness:

1. **Strict Disparity Check (Backward Check)**:

   - For every **Observed Point** (in Projector Space), is it far from *all* **Expected Points**?
   - *Logic*: If observed point $P\_{obs}$ has $dist(P\_{obs}, P\_{exp}) > 3.0$ for all $P\_{exp}$, then it is likely on top of an object (shifted by parallax).
   - *Why this works*: On the floor, dots align perfectly. On a token, the projection shifts. Because of the **jitter**, a shifted dot has a near-zero probability of landing exactly on a neighbor's expected position.
   - Result: `shifted_points` (High confidence object points).

1. **Occlusion Check (Forward Check)**:

   - For every **Expected Point** (in Projector Space), is there an **Observed Point** nearby?
   - *Logic*: If expected point $P\_{exp}$ has no $P\_{obs}$ within $3.0$ pixels, then the floor at that location is **Occluded** (potentially by a token).
   - Result: `occluded_zones` (Areas where floor is missing).

1. **Consensus**:

   - A valid token should ideally show both signals: we see points where they shouldn't be (`shifted_points`) AND don't see points where they should be (`occluded_zones`).
   - However, for implementation simplicity, we primarily cluster `shifted_points`. If a `shifted_point` cluster does not overlap with an `occluded_zone` (meaning we still see the floor underneath it?), it might be a reflection artifact and can be discarded.

### 3.4 Clustering

1. Group the `shifted_points` into clusters (tokens).

### 3.4 Token Extraction

1. **Clustering**: Group shifted points into candidate tokens.
   - *Algorithm*: Iterate through shifted points. For each point, check if it belongs to an existing cluster (distance < `1.5 * spacing`). If yes, add to cluster. If no, start new cluster. Merge overlapping clusters if necessary.
1. **Filtering**: Discard clusters with $< 2$ points (noise/edge cases).
1. **Centroid**: The final `Token.world_x, world_y` is the mean of the cluster's coordinates.

## 4. Implementation Plan

### 4.1 Data Structures & Configuration

- **File**: `src/light_map/common_types.py`
  - **New Enum**: `TokenDetectionAlgorithm` (`FLASH`, `STRUCTURED_LIGHT`).
  - **New MenuAction**: `SCAN_ALGORITHM`.
- **File**: `src/light_map/map_config.py`
  - **Class**: `GlobalMapConfig`: Add `detection_algorithm: TokenDetectionAlgorithm`.

### 4.2 Token Tracker Refactoring (`src/light_map/token_tracker.py`)

- Refactor `detect_tokens` to accept `frame_pattern` and `frame_dark`.
- Implement `_detect_dot_grid(frame_pattern, frame_dark, ...)`: The disparity logic.
- Add `get_scan_pattern(algorithm, width, height, ppi)` to generate the projection image.

### 4.3 Scene Updates (`src/light_map/scenes/scanning_scene.py`)

- **State Machine Update**: The scanning sequence must be strictly timed to handle projector/camera latency.
  - `ScanStage.PREPARE_DARK`: Project black.
  - `ScanStage.WAIT_DARK`: Wait 500ms.
  - `ScanStage.CAPTURE_DARK`: Capture frame.
  - `ScanStage.PREPARE_PATTERN`: Project pattern.
  - `ScanStage.WAIT_PATTERN`: Wait 500ms.
  - `ScanStage.CAPTURE_PATTERN`: Capture frame.
  - `ScanStage.PROCESS`: Run detection.
- **Rendering**: `ScanningScene.render` needs to return the correct image (black or pattern) based on the current stage.

### 4.4 UI Integration (`src/light_map/menu_builder.py`)

- Add a "Scan Algorithm" toggle in the "Settings" or "Session" menu.
- Persist the choice in `map_state.json`.

## 5. Rationale

- **Contrast Independence**: Works even if a token matches the map color (e.g., green mini on green forest).
- **Robustness**: Explicitly uses 3D geometry. Flat map features cannot cause coordinate shifts after unwarping.
- **Why keep Flash?**
  - **Speed**: Flash is computationally cheaper (simple thresholding).
  - **Simplicity**: Flash works well for high-contrast scenarios and is less sensitive to minor calibration drift.
- **Speed of Dot Grid**: $O(1)$ neighbor lookup via rounding makes the geometric approach viable within the \<1s processing budget.

## 6. Testing Strategy

### 6.1 Unit Tests

- **`tests/test_token_tracker.py`**:
  - **Pattern Generation**: Verify `get_scan_pattern` adapts density to PPI.
  - **Synthetic Detection**: Mock `projector_matrix` and input frames (pattern & dark). Verify subtraction works and shifts are detected.
- **`tests/test_scanning_scene.py`**: Verify the state machine transitions and timing delays (using mocked time).

### 6.2 Integration Tests

- **Manual**:
  1. Toggle to `STRUCTURED_LIGHT`.
  1. Place a token.
  1. Verify detection works even in moderate ambient light (due to background subtraction).

## 7. Alternatives Considered

### 7.1 Digital Image Correlation (DIC)

We considered using Full-Field Digital Image Correlation to compute a dense displacement map.

- **Pros**:
  - **Dense Depth Map**: Provides displacement vectors for every pixel, allowing detection of object shape/volume rather than just points.
  - **Sub-pixel Accuracy**: High precision for subtle deformations.
- **Cons**:
  - **Computational Cost**: Full-field 2D correlation (FFT-based or sliding window) is computationally expensive ($O(N \\log N)$ or $O(N^2)$). It risks violating the \<1s processing budget on constrained hardware (Raspberry Pi 4) compared to the $O(1)$ lookup of the dot grid.
  - **Edge Discontinuities**: Standard DIC assumes surface continuity. It struggles with the sharp step-edges of tokens on a flat map, often producing noise at the very boundaries we need to detect.
  - **Focus Sensitivity**: DIC relies on high-frequency speckle patterns. If the projector focus is soft (common in tabletop setups with varying heights), contrast drops and correlation fails.
  - **Lighting Sensitivity**: Uniform speckle patterns are more easily washed out by ambient light than high-contrast, discrete dots.

**Decision**: We chose **Sparse Dot Grid Disparity** because:

1. **Binary Goal**: We only need to detect *presence* and *location*, not surface topology.
1. **Performance**: Centroid extraction is extremely fast and scalable.
1. **Robustness**: Discrete dots are more robust to defocus and ambient light than dense speckle patterns.
