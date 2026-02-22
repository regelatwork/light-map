# Improved Calibration and Marker Defaults (Design)

## 1. Goal

Enhance the user experience of Light Map by providing a global default configuration for ArUco markers and expanding the calibration process to include PPI and Camera Pose (Extrinsics) estimation for robust parallax correction.

## 2. Default ArUco Marker Configuration

To avoid repeated configuration for every map, the system will maintain a global repository of marker definitions.

### 2.1 Configuration Structure

**`GlobalMapConfig` (in `map_state.json`):**

```json
{
  "global": {
    "aruco_defaults": {
      "1": { "name": "Fighter", "type": "PC", "size": 1, "height_mm": 25.0 },
      "10": { "name": "Goblin", "type": "NPC", "size": 1, "height_mm": 15.0 },
      "50": { "name": "Dragon", "type": "NPC", "size": 3, "height_mm": 50.0 }
    },
    "projector_ppi": 96.0,
    "..." : "..."
  },
  "maps": {
    "maps/dungeon.svg": {
      "aruco_overrides": {
        "10": { "name": "Boss Goblin", "type": "NPC", "size": 2, "height_mm": 30.0 }
      }
    }
  }
}
```

- **Lookup Logic**: When a marker with ID $N$ is detected:
  1. Check `aruco_overrides` for the current map.
  2. If not found, check `aruco_defaults` in `GlobalMapConfig`.
  3. If still not found, use a generic "Unknown NPC" profile (size 1, height 10mm).

## 3. Expanded Projector Calibration

The `projector_calibration.py` script will be expanded into a multi-step interactive wizard.

### 3.1 Step 1: Homography (Table Alignment)
- Existing logic using the projected chessboard pattern.
- Computes $H_{cam\_to\_proj}$ and saves it.
- **Goal**: Establish the base plane $(Z=0)$.

### 3.2 Step 2: PPI Calibration (Physical Scale)
- Project two ArUco markers (ID 0 and 1) at a fixed projector distance.
- Ask the user to place two physical ArUco markers on the table at a known distance (e.g., 100mm).
- **CRITICAL**: The physical markers MUST be placed directly on the table surface ($Z=0$). If placed on tokens, parallax will skew the calculation.
- **Improved PPI**: Detect markers 0 and 1. Use the homography from Step 1 to map detected centers to projector space. Calculate PPI based on the known physical distance.

### 3.3 Step 3: Camera Pose Estimation (Extrinsics)
- To perform accurate parallax correction, the system needs the camera's 3D position relative to the table.
- **Action**:
  1. Project 4+ targets (circles with ArUco IDs) in the corners of the table.
  2. The user places tokens of **known height** $h$ on these targets.
  3. The system detects the markers at $(u, v)_{cam}$.
  4. Even if placement is slightly imprecise, the system uses $H_{cam\_to\_proj}$ to find the "Ground" $(X, Y)$ coordinates of the marker's center (as if it was on the floor).
  5. **Refinement**: Combine the $(X, Y, h)$ 3D points and their 2D camera projections $(u, v)$ with the $Z=0$ points from the chessboard calibration.
  6. Run `cv2.solvePnP` to compute rotation ($R$) and translation ($t$). This method is preferred over homography decomposition for its robustness and accuracy.
- **Output**: `camera_extrinsics.npz` containing $R$ and $t$.

## 4. Implementation Strategy

### 4.1 Data Structures
- Update `GlobalMapConfig` and `MapEntry` in `src/light_map/map_config.py`.
- Add `aruco_defaults` and `aruco_overrides` fields.

### 4.2 Calibration Wizard (`projector_calibration.py`)
- Transition from a single-shot script to a loop-based interactive CLI (or reuse scenes from `InteractiveApp` if possible).
- Add functions:
  - `calibrate_ppi()`
  - `calibrate_extrinsics(heights: Dict[int, float])`

### 4.3 Scene Updates
- `ProjectorCalibrationScene` in `src/light_map/scenes/calibration_scenes.py` should be updated to handle the new steps if the user triggers them via the menu.

## 5. Rationale

- **UX**: ArUco markers become "plug and play" across all maps.
- **Accuracy**: Explicitly measuring points at height $Z > 0$ provides significantly better parallax correction than decomposing a single-plane homography, especially for cameras with high lens distortion or steep viewing angles.
- **Robustness**: Using the homography to find the $(X, Y)$ base of an imprecisely placed token allows for user error during calibration while still maintaining mathematical rigor.

## 6. Testing Strategy

- **Mock Pose Estimation**: Test `solvePnP` with synthetic points and verify if it recovers the correct camera center.
- **Persistence**: Verify that `aruco_defaults` are correctly saved and loaded.
- **Overrides**: Test that map-specific overrides take precedence over global defaults.
