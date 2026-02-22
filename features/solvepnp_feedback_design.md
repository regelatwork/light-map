# Design: User Feedback for solvePnP Residuals

## 1. Goal
When performing the new multi-step projector calibration (specifically Step 3: Camera Pose Estimation), the system uses `cv2.solvePnP` to find the camera's position relative to the table. It is critical to inform the user of the *quality* of this calibration so they can decide whether to accept it or retry (e.g., if a token was placed incorrectly).

## 2. Metrics

### 2.1 Reprojection Error (RMS)
The primary metric for calibration quality is the **Root Mean Square (RMS) Reprojection Error**.
- **Definition**: The square root of the average squared distance (in pixels) between the *detected* 2D marker centers and the *reprojected* 3D world points.
- **Formula**: $RMS = \sqrt{\frac{1}{N} \sum_{i=1}^{N} ||p_{detected}^{(i)} - p_{reprojected}^{(i)}||^2}$

### 2.2 Per-Point Residuals
To help the user identify *which* specific marker might be problematic (e.g., bumped out of place), we will calculate the error distance for each point individually.

## 3. Visualization Strategy

The feedback will be presented as an augmented reality overlay on the camera feed.

### 3.1 Visual Elements
1.  **Detected Points**: Marked with a **Green Cross** (+).
2.  **Reprojected Points**: Marked with a **Red Circle** (○).
3.  **Residual Vectors**: A line connecting the Green Cross to the Red Circle.
    -   **Length**: Directly proportional to the error magnitude.
    -   **Color Coding**:
        -   **Green**: Error < 2.0 pixels (Excellent)
        -   **Yellow**: 2.0 < Error < 5.0 pixels (Acceptable)
        -   **Red**: Error > 5.0 pixels (Poor - likely placement error)

### 3.2 Global Status HUD
A text overlay at the top of the screen will summarize the result:
-   **Text**: "Calibration Error: X.X px"
-   **Status Indicator**:
    -   **"Good"** (Green background)
    -   **"Fair"** (Yellow background)
    -   **"Poor"** (Red background)

## 4. Interaction Workflow

After the `solvePnP` calculation is complete, the scene will enter a `VALIDATION` state.

1.  **Display Feedback**: Show the Visual Elements and Global Status HUD described above.
2.  **Wait for User Decision**:
    -   **Accept**: User performs a **Victory (Peace)** gesture.
        -   Action: Save `camera_extrinsics.npz` and proceed.
    -   **Retry**: User performs a **Closed Fist** gesture (held for 2 seconds).
        -   Action: Discard results and return to the `CAPTURE` state to allow re-placing tokens.

## 5. Technical Implementation

-   **Scene**: `ProjectorCalibrationScene` (or new `ExtrinsicsCalibrationScene`).
-   **State Machine**: Add `VALIDATION` state.
-   **Rendering**:
    -   Use `cv2.projectPoints` to get the reprojected coordinates.
    -   Draw overlays using `cv2.line`, `cv2.circle`, `cv2.putText`.
-   **Thresholds**:
    -   `ERROR_THRESHOLD_GOOD = 2.0`
    -   `ERROR_THRESHOLD_POOR = 5.0`
    -   (These values should be tunable in `map_config` eventually).

## 6. Open Questions
-   Should we automatically reject if error is > 10px? (Decision: No, let the user decide, but show a flashing warning).
-   What is the best gesture for "Retry"? (Decision: **Closed Fist** held for 2s to "Reset", as Thumbs Down is not currently supported by `gestures.py`).
