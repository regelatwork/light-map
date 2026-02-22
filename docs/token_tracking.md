# Token Tracking & Session Persistence

The Light Map system can detect physical tokens (minis, dice, terrain) and synchronize their positions with the digital map. It supports multiple detection strategies to balance accuracy, speed, and ease of use.

______________________________________________________________________

## 1. ArUco-Based Tracking

ArUco markers provide the most robust and continuous tracking. Each token is identified by a unique ID, allowing the system to track specific NPCs or PCs.

### Parallax Correction

Because the camera is offset from the projector, a marker on top of a 2-inch tall token will appear shifted (parallax error). The system corrects this by:

1. Using the camera's 3D pose (from **Extrinsics Calibration**).
1. Back-projecting a ray from the camera through the detected marker.
1. Intersecting that ray with a plane at the token's configured `height_mm`.
1. This finds the true $(X, Y)$ coordinate of the token's base on the table.

### Configuration (`map_state.json`)

You can define token properties in `map_state.json`. The system resolves properties in this order:

1. **Map Overrides**: Specific settings for a token on a particular map.
1. **Global Defaults**: Shared settings for a token ID across all maps.
1. **Generic Fallback**: Default values if no configuration is found.

#### Token Profiles

Common dimensions are abstracted into named profiles (e.g., `small`, `medium`, `large`).

```json
"token_profiles": {
  "small": { "size": 1, "height_mm": 15.0 },
  "medium": { "size": 1, "height_mm": 25.0 },
  "large": { "size": 2, "height_mm": 40.0 }
}
```

______________________________________________________________________

## 2. Flash-Based Detection

Best for tokens without ArUco markers (e.g., standard unpainted minis or terrain).

### How it works

1. **Flash**: The projector momentarily flashes full white to provide maximum contrast and "wash out" the underlying digital map.
1. **Segmentation**: Uses Adaptive Thresholding and Watershed segmentation to identify physical blobs.
1. **Grid Snapping**: If a grid is calibrated, blobs are snapped to the nearest cell.

### Adaptive Flash Calibration

To ensure the flash doesn't saturate the camera (making everything white), use **Session > Calibrate Flash**. The system will find the highest brightness level that still allows for clear segmentation.

______________________________________________________________________

## 3. Structured Light Detection

A secondary non-ArUco method that is robust to dark-colored tokens or low-contrast environments.

### How it works

1. **Project Pattern**: A jittered dot grid is projected.
1. **Analyze Disparity**: The system compares the observed dot positions against their expected positions on a flat surface.
1. **Detection**: Dots that are shifted or missing indicate an object with height (a token).

______________________________________________________________________

## 4. Visual Feedback & States

The renderer provides real-time feedback on the tracking state:

- **Locked Token**: A solid circle (cyan for NPCs, green for PCs) indicates a successfully tracked token.
- **Unknown Marker**: A **dashed outline** or question mark indicates a detected ArUco ID that is not in the configuration.
- **Duplicate IDs**: If the same ArUco ID is detected in multiple locations, the system selects the most stable (largest area) detection. Duplicates are ignored to prevent "flickering" between positions.
- **Ghost Tokens**: When loading a session, cyan outlines show the *saved* positions of tokens, helping you place physical minis back where they were.

______________________________________________________________________

## 5. Session Management

### Scan & Save

Select **Session > Scan & Save**. The system will:

1. Perform a Flash or Structured Light scan.
1. Save token IDs, $(X, Y)$ positions, and the current map viewport to a session file in `sessions/`.
1. Link the session to the specific map file (using a unique hash).

### Loading a Session

Select **Load Session** from the Maps menu. This restores the viewport and displays **Ghost Tokens** for manual alignment.

______________________________________________________________________

## 6. Troubleshooting

| Issue | Cause | Solution |
| :--- | :--- | :--- |
| **Token flickering** | Hand occlusion | Ensure hands aren't covering markers during interaction. |
| **Tokens "floating"** | Wrong height config | Verify the `height_mm` in `map_state.json` matches the physical token. |
| **No tokens detected (Flash)** | Exposure too high | Run **Calibrate Flash** to find the optimal intensity. |
| **Markers not detected** | Glare / Reflection | Use matte-finish marker prints or adjust room lighting. |
| **Misalignment at edges** | Projector distortion | Ensure Projector Calibration includes non-linear correction. |
