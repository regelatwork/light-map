# Token Tracking & Session Persistence (Design)

## Goal
Enable the system to detect physical tokens (minis, dice, coins) on the table, map their positions to the digital grid, and save/restore this session state.

## 1. The Challenge: Projector Interference
The projected map changes the color and appearance of tokens, making detection difficult.
- **Solution**: **"Flash Scan"**.
- **Mechanism**: The projector switches to **Full White (Level 255)** for a short burst (e.g., 1.5s).
- **Why**: This acts as a camera flash, illuminating all physical objects evenly against the white background.
- **Result**: Tokens appear as **dark silhouettes** or distinct colored blobs against the bright white table.

## 2. Detection Algorithm (OpenCV)

### A. Preprocessing
1.  **Capture**: Take a frame during the White Flash.
2.  **Warp**: Transform the camera image to a **Top-Down View** using the calibrated `projector_matrix`. This removes perspective distortion on the table plane.
3.  **Background Subtraction**: Optional, but helpful if lighting is uneven. (White Frame - Empty White Frame).

### B. Segmentation & Separation
To handle **adjacent tokens** (which appear as a single merged blob):
1.  **Threshold**: Convert to a Binary Image (Black/White).
2.  **Distance Transform**: Calculate the distance from each white pixel to the nearest black background pixel.
    *   *Result*: The center of each token becomes a "peak" (high intensity).
    *   *Effect*: Even if tokens touch, their centers remain distinct peaks.
3.  **Peak Detection**: Find local maxima in the distance map. These are the **Token Centers**.
4.  **Watershed Algorithm** (Optional): If we need precise outlines, use the peaks as markers to flood-fill the basins and separate the touching blobs.

### C. Coordinate Mapping
1.  **Pixel to World**: Convert the pixel coordinates of the peaks $(x, y)$ to World/SVG coordinates using `MapSystem.screen_to_world()`.
2.  **Grid Snapping**:
    *   Load `grid_spacing_svg` from `MapConfig`.
    *   Snap each token's world coordinate to the nearest grid cell center (or intersection).
    *   *Constraint*: Verify that the snapped position is within a valid distance (e.g., < 0.4 grid units) to avoid snapping noise.

## 3. Persistence (`session.json`)
Save the state of the "World":
```json
{
  "map_file": "dungeon_level_1.svg",
  "view": { "x": 100, "y": 200, "zoom": 1.5, "rotation": 0 },
  "tokens": [
    { "id": 1, "world_x": 50.5, "world_y": 60.2, "snapped_grid_x": 1, "snapped_grid_y": 2 }
  ]
}
```

## 4. User Experience (UX)

### Saving a Session
1.  **Trigger**: "Session > Scan & Save".
2.  **Action**: 
    -   System flashes White (Level 255).
    -   Captures frame.
    -   Detects tokens.
    -   Snaps to grid.
    -   Saves `session.json`.
3.  **Feedback**: "Session Saved! 5 Tokens detected."

### Restoring a Session
1.  **Trigger**: "Session > Load Session".
2.  **Action**:
    -   Loads map and view.
    -   Renders **"Ghost Tokens"** (Translucent circles) at saved coordinates.
3.  **Interaction**:
    -   User places physical tokens on the ghosts.
    -   System can optionally "Scan & Verify" to confirm placement (Green Flash if correct, Red highlight if missing).

## 5. Outstanding Questions
-   **Token Height**: Tall tokens (tents) might have their "center of mass" shifted by perspective.
    -   *Mitigation*: Use the **bottom-most point** of the blob (the base) or the peak of the distance transform (which tends to be central) as the anchor.
-   **Lighting**: Does ambient light interfere? (Flash 255 seems robust so far).
