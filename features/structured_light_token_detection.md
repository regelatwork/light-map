# Structured Light Token Detection

## 1. Goal
To implement a robust token detection algorithm that leverages structured light (specifically **Dot Grid Disparity**) to distinguish physical tokens from the flat map surface. This provides an alternative to the current contrast-based "Flash" method, which can fail when token colors match the map background.

## 2. Core Concept: Dot Grid Disparity
The algorithm relies on the geometric relationship between the camera and the projector. Since they are at different physical positions, objects with height (tokens) will cause a parallax shift in the observed position of projected patterns compared to the flat surface (map).

### Validated Logic
*   **Existing Homography**: The `projector_matrix` ($H$) transforms points from **Camera Space** $\to$ **Projector Space**.
*   **Planar Assumption**: The calibration assumes the map is a flat plane. Any deviation in height ($z > 0$) results in a coordinate shift when viewed from the camera's offset angle.
*   **Mechanism**:
    1.  Project a grid of dots at known projector coordinates $P_{expected}$.
    2.  Camera observes dots at $P_{cam}$.
    3.  Transform observed points: $P'_{proj} = H \cdot P_{cam}$.
    4.  **Disparity**: On the flat calibrated surface, $P'_{proj} \approx P_{expected}$. If a token is present, the height $h$ causes a shift, so $||P'_{proj} - P_{expected}|| > \text{threshold}$.

## 3. Detailed Technical Specifications

### 3.1 Pattern Generation (`get_scan_pattern`)
The tracker generates a deterministic dot grid to ensure we know exactly where every dot *should* be.

*   **Parameters**: `width`, `height`, `spacing=40`.
*   **Algorithm**:
    1.  Create a black image: `img = np.zeros((height, width), dtype=np.uint8)`.
    2.  Calculate start offsets: `ox, oy = spacing // 2, spacing // 2`.
    3.  Iterate:
        ```python
        expected_points = []
        for y in range(oy, height, spacing):
            for x in range(ox, width, spacing):
                cv2.circle(img, (x, y), radius=2, color=255, thickness=-1)
                expected_points.append((x, y))
        ```
    4.  The `expected_points` list is used during detection for comparison.

### 3.2 Dot Detection (Camera Frame)
1.  **Preprocessing**: Apply a simple threshold to find the white dots against the blacked-out map.
    ```python
    _, thresh = cv2.threshold(gray_frame, 200, 255, cv2.THRESH_BINARY)
    ```
2.  **Centroid Extraction**: Use `cv2.connectedComponentsWithStats` to find the precise center of each observed dot.
    ```python
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(thresh)
    # Filter by area (e.g., stats[i, cv2.CC_STAT_AREA]) to ignore noise
    observed_cam_pts = centroids[1:] # Skip background label 0
    ```

### 3.3 Shift Detection & Math
1.  **Transform to Projector Space**:
    Apply the homography to the camera centroids to find where they "land" in the projector's 2D coordinate system.
    ```python
    # pts_cam is (N, 1, 2)
    pts_proj_observed = cv2.perspectiveTransform(pts_cam, projector_matrix)
    ```
2.  **Neighbor Matching**:
    For each `p_obs` in `pts_proj_observed`, find the nearest `p_exp` in the generated `expected_points`. 
    *Note: Since the grid is regular, this can be done in $O(1)$ by rounding:*
    ```python
    gx = round((p_obs.x - ox) / spacing)
    gy = round((p_obs.y - oy) / spacing)
    p_exp = (ox + gx * spacing, oy + gy * spacing)
    ```
3.  **Disparity Calculation**:
    Calculate the Euclidean distance: $D = \sqrt{(x_{obs} - x_{exp})^2 + (y_{obs} - y_{exp})^2}$
4.  **Thresholding**:
    A point is marked as **Shifted** if $D > \text{threshold}$ (e.g., 8 pixels).
    *   **Rationale**: Small $D$ (1-3px) is likely jitter or minor calibration error. Large $D$ (>5px) indicates the dot hit a 3D object.

### 3.4 Token Extraction
1.  **Clustering**: Shifted points are grouped using a distance-based cluster (e.g., Euclidean distance between points < 1.5 * spacing). A single token (1" diameter) will typically intercept multiple dots.
2.  **Filtering**: Clusters with too few points are discarded as noise.
3.  **Centroid**: The final `Token.world_x, world_y` is the mean of the cluster's coordinates.

## 4. Implementation Plan

### 4.1 Data Structures & Configuration
*   **File**: `src/light_map/common_types.py`
    *   **New Enum**: `TokenDetectionAlgorithm` (`FLASH`, `STRUCTURED_LIGHT`).
    *   **New MenuAction**: `SCAN_ALGORITHM`.
*   **File**: `src/light_map/map_config.py`
    *   **Class**: `GlobalMapConfig`: Add `detection_algorithm: TokenDetectionAlgorithm`.

### 4.2 Token Tracker Refactoring (`src/light_map/token_tracker.py`)
*   Refactor `detect_tokens` to dispatch based on the selected algorithm.
*   Implement `_detect_flash(frame, ...)`: Existing logic.
*   Implement `_detect_dot_grid(frame, ...)`: The disparity logic described above.
*   Add `get_scan_pattern(algorithm, width, height)` to generate the projection image.

### 4.3 Scene Updates (`src/light_map/scenes/scanning_scene.py`)
*   Update the state machine to ask `TokenTracker` for the "Scan Pattern" image.
*   **Stage Update**: Ensure the map is blacked out during `STRUCTURED_LIGHT` projection to maximize dot contrast.

### 4.4 UI Integration (`src/light_map/menu_builder.py`)
*   Add a "Scan Algorithm" toggle in the "Settings" or "Session" menu.
*   Persist the choice in `map_state.json`.

## 5. Rationale
*   **Contrast Independence**: Works even if a token matches the map color (e.g., green mini on green forest).
*   **Robustness**: Explicitly uses 3D geometry. Flat map features cannot cause coordinate shifts after unwarping.
*   **Why keep Flash?**
    *   **Speed**: Flash is computationally cheaper (simple thresholding).
    *   **Simplicity**: Flash works well for high-contrast scenarios and is less sensitive to minor calibration drift.
*   **Speed of Dot Grid**: $O(1)$ neighbor lookup via rounding makes the geometric approach viable within the <1s processing budget.

## 6. Testing Strategy

### 6.1 Unit Tests
*   **`tests/test_token_tracker.py`**:
    *   **Pattern Generation**: Verify `get_scan_pattern` returns correct dimensions and dot counts.
    *   **Synthetic Detection**: Mock `projector_matrix` and a frame where one dot is manually shifted. Verify 1 token is detected.
    *   **Noise Test**: Verify 0 detections on a perfectly aligned flat frame.
*   **`tests/test_map_config.py`**: Verify persistence of the `detection_algorithm` setting.

### 6.2 Integration Tests
*   **Manual**:
    1.  Toggle to `STRUCTURED_LIGHT`.
    2.  Place a token, verify detection.
    3.  Verify detection works even if token color matches map color.
