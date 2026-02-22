# ArUco-Based Token Tracking (Design)

## 1. Goal

Implement a robust, continuous token tracking system using ArUco markers placed on top of physical gaming tokens. This system will enable real-time interaction with digital maps, supporting various token sizes and providing resilience against temporary occlusions.

## 2. Core Concepts

### 2.1 ArUco Markers
ArUco markers provide a unique ID for each token, allowing the system to distinguish between Player Characters (PCs) and Non-Player Characters (NPCs). They are highly robust to lighting variations and can be detected without the disruptive "Flash Scan" required by other methods.

### 2.2 The Elevation Challenge (Parallax)
Tokens have a physical height $h$. ArUco markers are placed on the *top* surface. Because the camera is offset from the projector's optical axis, the detected position of a marker on top of a token will be shifted (parallax error) compared to its actual base position on the table.

**Correction Strategy:**
1.  **Camera Pose Estimation**: Decompose the existing Projector-Camera Homography ($H$) using the Camera Intrinsics ($K$) to find the camera's rotation ($R$) and translation ($t$) relative to the table plane ($z=0$).
2.  **Ray-Plane Intersection**: For a detected marker center $(u, v)$ in the camera frame:
    - Back-project to a 3D ray in camera space.
    - Transform the ray to table space using $(R, t)$.
    - Intersect the ray with the plane $z=h$ (where $h$ is the token height).
    - The resulting $(X, Y)$ coordinates represent the true center of the token's base on the table.

## 3. Technical Specifications

### 3.1 Token Configuration
A new configuration section in `map_state.json` will map ArUco IDs to token properties:

```json
{
  "aruco_tokens": {
    "1": { "name": "Fighter", "type": "PC", "size": 1, "height_mm": 25.0 },
    "10": { "name": "Goblin 1", "type": "NPC", "size": 1, "height_mm": 15.0 },
    "50": { "name": "Dragon", "type": "NPC", "size": 3, "height_mm": 50.0 }
  }
}
```

- **Size**: Number of grid cells occupied (e.g., $1 	imes 1$, $3 	imes 3$).
- **Height**: Used for parallax correction.

### 3.2 Detection Pipeline

1.  **Capture**: Continuous background capture (no flash).
2.  **ArUco Detection**: Use `cv2.aruco.ArucoDetector`.
3.  **Parallax Correction**: Apply the ray-plane intersection logic.
4.  **Coordinate Mapping**:
    - Table (mm) $	o$ Projector (pixels) using PPI.
    - Projector $	o$ World (SVG) using `MapSystem.screen_to_world`.
5.  **Grid Snapping**:
    - Calculate `grid_x, grid_y` based on `grid_origin` and `grid_spacing`.
    - For $n 	imes n$ tokens, snap the centroid to the intersection or center that aligns the footprint with the grid.
6.  **Temporal Filtering**:
    - Maintain a "Last Seen" state for each ID.
    - Use an Alpha-Beta filter or Kalman filter to smooth movement.
    - If a marker is lost, keep it at its last known position for $N$ frames (handling hand occlusions).

### 3.3 Integration Architecture

#### A. `ArucoTokenDetector` (`src/light_map/vision/aruco_detector.py`)
A new detector class following the pattern of `FlashTokenDetector`.

#### B. `TokenTracker` Updates (`src/light_map/token_tracker.py`)
Add `TokenDetectionAlgorithm.ARUCO` and delegate to the new detector.

#### C. `InteractiveApp` Updates
- Support continuous scanning in the background or as a dedicated high-frequency mode.
- Update `AppContext` to store ArUco configuration.

## 4. User Experience (UX)

- **Continuous Tracking**: Tokens move on the digital map as they are moved physically.
- **Visual Feedback**: A digital highlight (e.g., a circle or the token's name) is projected around/under the physical token.
- **Classification**: PCs can have distinct colors/highlights compared to NPCs.

## 5. Implementation Plan

1.  **Research**: Verify homography decomposition accuracy with current calibration data.
2.  **Core Logic**: Implement `ArucoTokenDetector` with parallax correction.
3.  **Config**: Add ArUco token mapping to `MapConfigManager`.
4.  **UI**: Add ArUco detection toggle to the menu.
5.  **Validation**: Test with physical tokens of different heights and sizes.

## 6. Testing Strategy

- **Synthetic Tests**: Mock camera detections and verify parallax correction math.
- **Offline Tests**: Use recorded video of ArUco markers at known heights.
- **Integration Tests**: Verify grid snapping for $1 	imes 1$ and $3 	imes 3$ tokens.
