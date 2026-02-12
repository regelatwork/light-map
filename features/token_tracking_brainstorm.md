# Token Tracking & Session Persistence (Design)

## Goal
Enable the system to detect physical tokens (minis, dice, coins) on the table, map their positions to the digital grid, and save/restore this session state.

## 1. The Challenge: Projector Interference & Synchronization
The projected map changes the color and appearance of tokens, making detection difficult. A "Flash Scan" (switching to full white) is required, but this introduces latency and exposure challenges.

### Critical Risks & Mitigations
1.  **Projector Latency**: Projectors have input lag. Switching to White (255) takes time to settle.
    *   **Mitigation**: **Multi-Frame Capture Sequence**. Display White -> Wait 500ms (settling) -> Flush Camera Buffer -> Capture Frame.
2.  **Camera Exposure**: A sudden bright flash causes auto-exposure to darken the image, potentially losing token details.
    *   **Mitigation**: **Exposure Locking** (if possible via `v4l2-ctl`) or **Discard Initial Frames** to allow auto-exposure to stabilize on the high-brightness scene.
3.  **UI Blocking**: The flash is disruptive. The UI must block interaction during the scan.
    *   **Mitigation**: Introduce `AppMode.SCANNING` to `InteractiveApp`.

## 2. Architecture & Class Structure

### A. Data Structures (`src/light_map/common_types.py`)
```python
@dataclass
class Token:
    id: int
    world_x: float  # SVG coordinates
    world_y: float
    grid_x: int     # Snapped grid coordinates (optional)
    grid_y: int
    confidence: float = 1.0
```

### B. Core Logic (`src/light_map/token_tracker.py`)
Encapsulates the OpenCV pipeline. Stateless or minimal state.

**Key Methods:**
*   `detect_tokens(frame_white: np.ndarray, frame_dark: np.ndarray, projector_matrix: np.ndarray, map_system: MapSystem) -> List[Token]`
    *   Accepts `frame_white` (L255) and optionally `frame_dark` (L50/L150) for background subtraction.
    *   Performs perspective warp (using `projector_matrix`).
    *   Runs segmentation logic (Threshold -> Distance Transform -> Watershed).
    *   Converts pixel coordinates to world coordinates via `map_system.screen_to_world()`.
    *   Snaps to grid using `MapConfig`.

### C. Persistence (`src/light_map/session_manager.py`)
Handles saving/loading `session.json`.

**Key Methods:**
*   `save_session(filename: str, map_name: str, viewport: ViewportState, tokens: List[Token])`
*   `load_session(filename: str) -> SessionData`

### D. Integration (`src/light_map/interactive_app.py`)
*   **New Mode**: `AppMode.SCANNING`.
*   **State Machine**:
    1.  **Trigger**: User selects "Scan".
    2.  **Enter SCANNING Mode**: Stop rendering map/menu.
    3.  **Render White**: Output full white frame.
    4.  **Wait**: Sleep 0.5s (or X frames).
    5.  **Capture**: Read frame from `Camera`.
    6.  **Process**: Call `TokenTracker.detect_tokens()`.
    7.  **Restore**: Switch back to `AppMode.MENU` / `AppMode.MAP`.

## 3. Detection Algorithm (OpenCV)

### A. Preprocessing
1.  **Capture**: Take `frame_white` (Flash) and `frame_dark` (Ambient/Map).
2.  **Difference**: `diff = cv2.absdiff(frame_white, frame_dark)` (Optional: Test if `frame_white - frame_empty` is better).
3.  **Warp**: Transform to Top-Down View using `projector_matrix`.

### B. Segmentation & Separation
To handle **adjacent tokens** (merged blobs):
1.  **Threshold**: Binary threshold (Adaptive or Otsu).
2.  **Distance Transform**: `cv2.distanceTransform`. Centers of tokens become bright peaks.
3.  **Peak Detection**: `cv2.minMaxLoc` or finding local maxima.
4.  **Watershed**: Use peaks as markers to segment touching blobs.

### C. Coordinate Mapping
1.  **Pixel to World**: `MapSystem.screen_to_world(px, py)` -> `(wx, wy)`.
2.  **Grid Snapping**:
    *   Load `grid_spacing_svg` from `MapConfig`.
    *   Snap `(wx, wy)` to nearest grid intersection/center.

## 4. Verification & Testing Strategy

### A. Offline Verification (`tests/test_token_tracker_offline.py`)
Use the captured samples in `samples/` to tune the CV pipeline without hardware.
*   **Data Source**:
    *   `samples/token_capture_20260211_235147_L255.png` (Flash)
    *   `samples/token_capture_20260211_235143_L50.png` (Dark/Ambient)
*   **System State Metadata (for `maps/bd514.svg` context)**:
    ```json
    {
      "projector_ppi": 54.108272552490234,
      "map_file": "maps/bd514.svg",
      "grid_spacing_svg": 31.33882551291452,
      "viewport": {
        "x": 18.57794105122582,
        "y": 392.520418453934,
        "zoom": 1.2807659034653744,
        "rotation": 90.0
      },
      "projector_matrix": [
        [-1.8409932405453235, -0.14534538953716655, 2823.0021220211647],
        [0.2909438616112758, -1.8224593534761375, 1103.4384854877414],
        [-2.2959382562043752e-05, 0.0001431765260352377, 1.0]
      ]
    }
    ```
    *Note: This metadata is CRITICAL. If the physical setup (camera/projector) changes, `projector_matrix` will change, invalidating the perspective warp for these samples.*

*   **Metadata**: Create JSON sidecars for samples defining "Ground Truth" token positions.
*   **Tests**:
    *   **Touching Tokens**: Verify watershed separates the adjacent tokens in the sample.
    *   **Empty Table**: Verify zero detection on empty table (needs new sample or masked region).

### B. Integration Tests
*   **Coordinate Transform**: Verify `screen_to_world` accuracy under rotation (0, 90, 180, 270).

## 5. Persistence (`session.json`)
```json
{
  "version": 1,
  "map_file": "maps/bd514.svg",
  "timestamp": "2026-02-12T10:00:00",
  "view": { "x": 100, "y": 200, "zoom": 1.5, "rotation": 0 },
  "tokens": [
    { "id": 1, "world_x": 50.5, "world_y": 60.2, "grid_x": 1, "grid_y": 2 }
  ]
}
```

## 6. User Experience (UX)

### Saving
1.  **Trigger**: "Session > Scan & Save".
2.  **Feedback**: "Stand Clear... Scanning..." -> White Flash -> "Saved X Tokens".

### Restoring
1.  **Trigger**: "Session > Load".
2.  **Action**:
    *   Load Map & Viewport.
    *   Render "Ghost Tokens" (Translucent circles) at `world_x, world_y`.
