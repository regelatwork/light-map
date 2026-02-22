# ArUco-Based Token Tracking (Design)

## 1. Goal

Implement a robust, continuous token tracking system using ArUco markers placed on top of physical gaming tokens. This system will enable real-time interaction with digital maps, supporting various token sizes and providing resilience against temporary occlusions.

## 2. Core Concepts

### 2.1 ArUco Markers

ArUco markers provide a unique ID for each token, allowing the system to distinguish between Player Characters (PCs) and Non-Player Characters (NPCs). They are highly robust to lighting variations and can be detected without the disruptive "Flash Scan" required by other methods.

### 2.2 The Elevation Challenge (Parallax)

Tokens have a physical height $h$. ArUco markers are placed on the *top* surface. Because the camera is offset from the projector's optical axis, the detected position of a marker on top of a token will be shifted (parallax error) compared to its actual base position on the table.

**Correction Strategy:**

1. **Camera Pose Estimation**: Use the camera's rotation ($R$) and translation ($t$) obtained via `cv2.solvePnP` during the expanded projector calibration wizard (stored in `camera_extrinsics.npz`).
1. **Ray-Plane Intersection**: For a detected marker center $(u, v)$ in the camera frame:
   - Back-project to a 3D ray in camera space using the camera intrinsics ($K$).
   - Transform the ray to table space using $(R, t)$.
   - Intersect the ray with the plane $z=h$ (where $h$ is the token height).
   - The resulting $(X, Y)$ coordinates represent the true center of the token's base on the table (Table Space).

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

- **Size**: Number of grid cells occupied (e.g., $1 imes 1$, $3 imes 3$).
- **Height**: Used for parallax correction.

### 3.2 Detection Pipeline

1. **Capture**: Continuous background capture (no flash).
1. **ArUco Detection**: Use `cv2.aruco.ArucoDetector`.
1. **Parallax Correction**: Apply the ray-plane intersection logic to obtain $(X, Y)\_{table}$.
1. **Coordinate Mapping**:
   - **Table to Projector**: $(X, Y)\_{table}$ to Projector coordinates using PPI.
   - **Projector to World**: Projector coordinates to World (SVG) using `MapSystem.screen_to_world`.
1. **Grid Snapping**:
   - Calculate `grid_x, grid_y` based on `grid_origin` and `grid_spacing`.
   - **Odd Size ($n=1, 3, 5$):** Snap centroid to the **center** of a grid cell.
   - **Even Size ($n=2, 4$):** Snap centroid to the **intersection** (corner) of grid cells.
1. **Temporal Filtering**:
   - Maintain a "Last Seen" state for each ID.
   - Use an Alpha-Beta filter or Kalman filter to smooth movement.
   - **Occlusion Buffer Strategy:**
     - If a marker is lost (e.g., hand occlusion), keep it at its last known position for **2000ms**.
     - During this buffer period, the token's digital visualization (highlight/label) will **pulse** to indicate temporary tracking loss.
     - If the marker reappears within 2000ms, the pulsing stops and tracking resumes immediately.
     - If the timeout expires without re-detection, the token is removed from the map.

### 3.3 Integration Architecture

#### A. `ArucoTokenDetector` (`src/light_map/vision/aruco_detector.py`)

A new detector class following the pattern of `FlashTokenDetector`.

#### B. `TokenTracker` Updates (`src/light_map/token_tracker.py`)

Add `TokenDetectionAlgorithm.ARUCO` and delegate to the new detector.

#### C. `InteractiveApp` Updates

- Support continuous scanning in the background or as a dedicated high-frequency mode.
- Update `AppContext` to store ArUco configuration.

### 3.4 ID Management Strategy

#### A. Unknown IDs (Detected but not Configured)

When the system detects an ArUco ID that is *not* present in the `aruco_tokens` configuration:

1. **Instantiation**: The system immediately instantiates a temporary `Token` object.
1. **Default Properties**:
   - **Name**: "Unknown [ID]" (e.g., "Unknown 42").
   - **Type**: "Object" (Neutral).
   - **Size**: $1 \\times 1$ grid cell.
   - **Height**: Default standard base height (e.g., 5.0mm). *Note: This minimizes parallax over-correction for flat tokens, which is safer than assuming a tall height.*
   - **Color**: Neutral Gray or White highlight.
1. **Persistence**: These tokens are transient. They are not saved to `map_state.json` unless explicitly registered by the user.
1. **Visual Feedback**: Distinct "dashed" outline or "question mark" icon to indicate unconfigured status.

#### B. Duplicate IDs (Physical Conflicts)

In cases where the computer vision pipeline detects multiple instances of the *same* ArUco ID in a single frame (e.g., two physical tokens printed with ID 10):

1. **Strict Uniqueness**: The system enforces a 1-to-1 mapping between IDs and distinct tracked entities to ensure state persistence (HP, status effects).
1. **Conflict Resolution**:
   - The system tracks the **largest** or **most stable** marker detection as the valid token.
   - Secondary detections of the same ID are ignored or flagged with an error visualization (e.g., Red "Duplicate" warning).
   - *Rationale*: Prevents state-swapping bugs where "Goblin A" (10 HP) and "Goblin B" (Full HP) share an ID and the system confuses them.

## 4. User Experience (UX)

- **Continuous Tracking**: Tokens move on the digital map as they are moved physically.
- **Visual Feedback**: A digital highlight (e.g., a circle or the token's name) is projected around/under the physical token.
- **Classification**: PCs can have distinct colors/highlights compared to NPCs.

## 5. Implementation Plan

1. **Research**: Verify `solvePnP` accuracy with synthetic and physical calibration data.
1. **Core Logic**: Implement `ArucoTokenDetector` with parallax correction.
1. **Config**: Add ArUco token mapping to `MapConfigManager`.
1. **UI**: Add ArUco detection toggle to the menu.
1. **Validation**: Test with physical tokens of different heights and sizes.

## 6. Testing Strategy

- **Synthetic Tests**: Mock camera detections and verify parallax correction math.
- **Offline Tests**: Use recorded video of ArUco markers at known heights.
- **Integration Tests**: Verify grid snapping for $1 imes 1$ and $3 imes 3$ tokens.
