# Design Refinement: Token Tracking Stability (Ray-Plane vs. Pose Estimation)

## 1. Executive Summary

**Decision:** The system will utilize **Ray-Plane Intersection with Fixed Height** as the primary method for tracking ArUco token positions.

**Rationale:** Stability and jitter-reduction are prioritized over automatic height detection. Real-time 6DOF pose estimation (`solvePnP`) on small markers is inherently noisy in the Z-axis (depth), leading to "jittery" or "dancing" tokens on the digital map. Ray-Plane intersection, which relies on the marker's centroid and the pre-calibrated camera extrinsics, offers superior stability for the 2D tabletop context.

## 2. Analysis: The Two Approaches

### Option A: Real-Time Pose Estimation (`solvePnP`)

This method calculates the full 6-Degree-of-Freedom (6DOF) pose (Rotation $R$, Translation $t$) of the marker relative to the camera for every frame.

**Pros:**

- **Auto-Height Detection:** The $Z$ component of the translation vector (in table coordinates) automatically represents the token's height. No manual configuration is needed.
- **Full Orientation:** Captures pitch and roll, which could theoretically detect if a token is toppled.

**Cons:**

- **Instability (Jitter):** Monocular pose estimation is sensitive to pixel noise. For small markers (e.g., 20mm) viewed from a distance (e.g., 1m), a sub-pixel error in corner detection results in significant angular variance. This manifests as the token "wobbling" or "jumping" in Z, which projects to X/Y jitter on the map.
- **Ambiguity:** Square markers can suffer from "flip" ambiguity at certain angles, causing massive momentary spikes in position error.
- **Computational Cost:** `solvePnP` (iterative) is more expensive than simple ray casting, though likely negligible on modern hardware.

### Option B: Ray-Plane Intersection (Fixed Height)

This method uses the marker's 2D centroid $(u, v)$ in the image, back-projects it to a 3D ray using camera intrinsics, and finds the intersection of this ray with a horizontal plane at a configured height $Z = h\_{config}$.

**Pros:**

- **Superior Stability:** The centroid of a marker is the average of its 4 corners (or all black pixels). Averaging significantly reduces Gaussian noise.
- **Geometric Robustness:** By constraining the solution to a horizontal plane, we eliminate 3 degrees of freedom (Z, Pitch, Roll) that are the source of most noise.
- **Predictable Failure:** If the height is wrong, the error is a constant offset (parallax), not a random jitter. The token remains stable.

**Cons:**

- **Configuration Required:** The system must know the physical height ($h$) of the token to correct for parallax accurately.
- **Parallax Error:** If $h\_{config}
  eq h\_{actual}$, the projected position will be offset from the true position (away from the camera center).

## 3. Detailed Trade-off: The "Dancing" Token Problem

In a tabletop RPG setting, users expect digital avatars to stay "glued" to their physical counterparts.

- **Scenario:** A 25mm miniature with a 20mm marker.
- **Using `solvePnP`:** If the Z-estimation fluctuates by ±2mm (common for small markers), the projected X/Y position on the table can shift by ±1-2mm depending on the viewing angle. This creates a distracting vibration effect (5-10 pixels at typical projector resolutions).
- **Using Ray-Plane:** The centroid detection is typically stable to within < 0.1 pixels. The resulting projected ray is rock-solid. The token position is effectively static when the physical object is static.

## 4. Implementation Strategy

### 4.1 Core Tracking Logic

We will proceed with the strategy outlined in `features/aruco_token_tracking.md`:

1. **Detect** marker corners.
1. **Compute Centroid** $(u, v)$.
1. **Back-project** to Ray $R\_{cam}$.
1. **Transform** Ray to World Space $R\_{world}$ using calibrated camera extrinsics.
1. **Intersect** $R\_{world}$ with Plane $Z = h\_{token}$.

### 4.2 Handling Unknown Heights

Since we are rejecting auto-detection for runtime tracking, we need a strategy for unknown tokens:

- **Default Height:** New tokens default to a "Standard Base Height" (e.g., 3mm or 5mm). This is the height of a standard plastic base.
  - *Why?* Most parallax comes from the base itself. The marker is usually on the base. If the marker is on a tall object (e.g., a dragon's head), the user *must* configure it for accuracy, but a default base height is a safe baseline that minimizes "floating" behavior for the majority of tokens.

### 4.3 Future Feature: "Calibration Mode" (Best of Both Worlds)

To solve the configuration burden, we can introduce a **"Learn Token Height"** feature in the future:

1. User places a new token in the center of the camera view.
1. System runs `solvePnP` over 30-60 frames.
1. System **averages** the results to find a stable $Z\_{avg}$.
1. System saves this $Z\_{avg}$ as the `height_mm` for that token ID.
1. Runtime tracking reverts to **Ray-Plane Intersection** using this learned height.

## 5. Conclusion

We will **not** replace the Ray-Plane intersection model. The original design decision holds. The stability benefits outweigh the convenience of auto-detection.

**Next Steps:**

1. Update `features/aruco_token_tracking.md` to explicitly reference this decision rationale. (Optional, as the design already assumes Ray-Plane).
1. Proceed with implementation of `ArucoTokenDetector` using the Ray-Plane method.
