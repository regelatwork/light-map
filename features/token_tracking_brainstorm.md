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
    grid_x: Optional[int]
    grid_y: Optional[int]
    confidence: float = 1.0

@dataclass
class SessionData:
    map_file: str
    viewport: ViewportState
    tokens: List[Token]
    timestamp: str
```

### B. Core Logic (`src/light_map/token_tracker.py`)
Encapsulates the OpenCV pipeline. Stateless or minimal state.

**Key Methods:**
*   `detect_tokens(frame_white: np.ndarray, projector_matrix: np.ndarray, map_system: MapSystem, grid_spacing_svg: float, ppi: float) -> List[Token]`
    *   Accepts `frame_white` (L255) and optionally `frame_dark` (L50/L150) for background subtraction.
    *   Performs perspective warp (using `projector_matrix`).
    *   Runs segmentation logic (Adaptive Threshold -> Watershed).
    *   **Splitting Heuristic**: Checks aspect ratio of detected blobs. If `h > 1.6*w` or `w > 1.6*h`, splits the blob into 2 tokens to handle adjacent placement.
    *   Converts pixel coordinates to world coordinates via `map_system.screen_to_world()`.
    *   Snaps to grid using `MapConfig`.

### C. Persistence (`src/light_map/session_manager.py`)
Handles saving/loading `session.json`.

**Key Methods:**
*   `save_session(filepath: str, data: SessionData) -> bool`
*   `load_session(filepath: str) -> Optional[SessionData]`

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
1.  **Warp**: Transform to Top-Down View using `projector_matrix`.
2.  **Blur**: Gaussian Blur (9x9) to reduce internal texture noise.

### B. Segmentation & Separation
To handle **adjacent tokens** (merged blobs):
1.  **Threshold**: Adaptive Threshold (`ADAPTIVE_THRESH_GAUSSIAN_C`) handles uneven lighting.
2.  **Morphology**: Open then Close to remove noise and fill holes.
3.  **Distance Transform**: Centers of tokens become bright peaks.
4.  **Watershed**: Use peaks as markers to segment touching blobs.

### C. Heuristic Splitting
1.  **Aspect Ratio**: If a blob is significantly elongated (`> 1.6:1`), assume it's two tokens side-by-side (Horizontal or Vertical).
2.  **Division**: Split the bounding box geometrically and assign centers to sub-regions.

### D. Coordinate Mapping
1.  **Pixel to World**: `MapSystem.screen_to_world(px, py)` -> `(wx, wy)`.
2.  **Grid Snapping**:
    *   Load `grid_spacing_svg` from `MapConfig`.
    *   Snap `(wx, wy)` to nearest grid intersection/center if within `0.4` units.

## 4. Verification & Testing Strategy

### A. Offline Verification (`tests/test_token_tracker_offline.py`)
Use the captured samples in `samples/` to tune the CV pipeline without hardware.
*   **Data Source**: `samples/token_capture_20260211_235147_L255.png` (Flash)
*   **Tests**:
    *   **Touching Tokens**: Verify watershed separates the adjacent tokens in the sample.
    *   **Empty Table**: Verify zero detection on empty table (needs new sample or masked region).

### B. Integration Tests
*   **Coordinate Transform**: Verify `screen_to_world` accuracy under rotation (0, 90, 180, 270).

## 5. Persistence (`session.json`)
```json
{
  "map_file": "maps/bd514.svg",
  "timestamp": "2026-02-12T10:00:00",
  "viewport": { "x": 100, "y": 200, "zoom": 1.5, "rotation": 0 },
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
    *   Render "Ghost Tokens" (Cyan circles) at `world_x, world_y`.
