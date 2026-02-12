# Token Tracking & Session Persistence (Brainstorm)

## Goal
Enable the system to detect physical tokens (minis, dice, coins) on the table, map their positions to the digital grid, and save/restore this state to assist in setting up future sessions.

## 1. The Challenge: Projector Interference
The primary difficulty is that the map is projected *onto* the tokens, changing their color and appearance.
- **Problem**: A red dragon mini looks blue if it's standing on a blue ocean tile.
- **Problem**: The room is likely dark, so the camera relies on the projector for light.

## 2. Proposed Solution: "Flash Scan"
Instead of trying to subtract the map background in real-time, we use a controlled "Scan" sequence.

### Workflow
1.  **Trigger**: User selects "Session > Scan Tokens" from the menu.
2.  **Flash**: The projector switches to **Full White** for a short burst (e.g., 0.5s).
    - *Why?* This acts as a camera flash, illuminating all physical objects on the table evenly.
    - *Why not Black?* In a dark room, projecting black makes everything invisible.
3.  **Capture**: The camera captures a frame during the white flash.
4.  **Process**: The system detects "blobs" (contours) in the captured image.
5.  **Restore**: The projector returns to displaying the map.
6.  **Feedback**: "Ghost" circles appear on the map at the detected locations.

## 3. Technical Implementation

### A. Coordinate Transformation Chain
We can precisely map a camera pixel to a map coordinate:
1.  **Camera Frame** $(u, v)$
2.  $\xrightarrow{	ext{Homography}}$ **Projector/Screen** $(x, y)$
3.  $\xrightarrow{	ext{MapSystem}}$ **World/SVG** $(w_x, w_y)$

### B. Detection Algorithm (OpenCV)
1.  **Input**: "Flash" frame (White background + Objects).
2.  **Preprocessing**: Grayscale -> Gaussian Blur.
3.  **Thresholding**: Adaptive Thresholding (handles uneven lighting better than fixed).
4.  **Contour Finding**: `cv2.findContours`.
5.  **Filtering**:
    -   Ignore extremely large blobs (Hands/Arms).
    -   Ignore tiny specks (Sensor noise/Dust).
    -   *Constraint*: Min Area ~ 1cm², Max Area ~ 100cm².
6.  **Centroid**: Calculate center of mass for each contour.

### C. Persistence (`session.json`)
We save the state of the "World":
```json
{
  "map_file": "dungeon_level_1.svg",
  "view": { "x": 100, "y": 200, "zoom": 1.5, "rotation": 0 },
  "tokens": [
    { "id": 1, "world_x": 50.5, "world_y": 60.2, "radius_px": 20 }
  ]
}
```

## 4. User Experience (UX)

### Saving a Session
1.  User: "Scan & Save".
2.  System: Flashes White -> Captures -> Saves `session.json`.
3.  Feedback: "Session Saved! 5 Tokens detected."

### Restoring a Session
1.  User: "Load Session".
2.  System: Loads map, pans to correct view.
3.  System: Displays **"Ghost Tokens"** (Translucent White Circles with Dotted Outlines) at the saved coordinates.
4.  User: Places physical tokens on the ghosts.
5.  System (Loop):
    -   Continuously (or on demand) scans.
    -   If a physical token matches a Ghost location, the Ghost turns **Green** or disappears.
    -   *Refinement*: This continuous scan might be annoying (flashing).
    -   *Alternative*: User places tokens, then hits "Check Alignment". System flashes and highlights missing/misaligned tokens.

## 5. Potential Enhancements
-   **Token IDs**: Use ArUco markers on token bases to know *exactly* which monster is where.
-   **Fog of War**: Use token positions to reveal the map dynamically.
-   **Shadows**: Use the token position to digitally cast dynamic shadows from virtual light sources.

## Questions for Discussion
1.  **Table Surface**: Is it a whiteboard/paper (bright) or wood (dark)? This affects thresholding.
2.  **Token Types**: Are they standard 1-inch bases? Irregular shapes?
3.  **Lighting**: Can we assume the room is dark, or is there ambient light?
