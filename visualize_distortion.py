import cv2
import numpy as np
import os


def visualize_distortion(
    calib_file="projector_calibration.npz", output_file="distortion_field.png"
):
    if not os.path.exists(calib_file):
        print(f"Error: {calib_file} not found. Run projector_calibration.py first.")
        return

    # 1. Load Data
    data = np.load(calib_file)
    matrix = data["projector_matrix"]
    cam_pts = data["camera_points"]
    proj_pts = data["projector_points"]

    # Use projector_resolution if available, else fallback to standard logic
    if "projector_resolution" in data:
        width, height = data["projector_resolution"]
    elif "resolution" in data:
        # Legacy: Check if resolution field is actually projector size or camera size
        res = data["resolution"]
        # Basic heuristic: if it matches the current camera spec, it might be camera res
        # But for visualization we want the projector space.
        # If we don't have explicit projector_resolution, we assume the stored one is the target canvas.
        width, height = res[0], res[1]
    else:
        print("Warning: Missing resolution metadata. Falling back to 1920x1080.")
        width, height = 1920, 1080

    # 2. Calculate Theoretical (Homography) Points
    # Transformation: Camera -> Projector (Screen)
    src_pts = cam_pts.reshape(-1, 1, 2)
    theoretical_proj_pts = cv2.perspectiveTransform(src_pts, matrix).reshape(-1, 2)

    # 3. Calculate Residuals (Error Vectors)
    # Residual = Actual Projected Point - Theoretical Point (predicted by homography)
    # The actual projected point (proj_pts) is where the dot was drawn on the screen.
    # The theoretical point is where the homography map SAYS it should be given the camera view.
    # vector = Actual - Theoretical
    residuals = proj_pts - theoretical_proj_pts
    magnitudes = np.linalg.norm(residuals, axis=1)

    print("Distortion Statistics (Residuals):")
    print(f"  Mean:   {np.mean(magnitudes):.2f} px")
    print(f"  Max:    {np.max(magnitudes):.2f} px")
    print(f"  Median: {np.median(magnitudes):.2f} px")

    # 4. Draw Visualization
    # Create black canvas
    img = np.zeros((height, width, 3), dtype=np.uint8)

    # Scale factor for vectors (to make them visible)
    scale = 5.0

    # Draw grid intersections (theoretical)
    for p in theoretical_proj_pts:
        cv2.circle(img, (int(round(p[0])), int(round(p[1]))), 3, (100, 100, 100), -1)

    # Draw vectors
    for i in range(len(theoretical_proj_pts)):
        p1 = theoretical_proj_pts[i]
        vec = residuals[i]
        p2 = p1 + vec * scale

        # Color based on magnitude
        mag = magnitudes[i]
        # Red if high, Blue if low
        color = (255, 100, 100)  # Default Blue-ish
        if mag > 5.0:
            color = (100, 100, 255)  # Red-ish (BGR)

        cv2.arrowedLine(
            img,
            (int(round(p1[0])), int(round(p1[1]))),
            (int(round(p2[0])), int(round(p2[1]))),
            color,
            2,
            tipLength=0.3,
        )

    cv2.putText(
        img,
        f"Max Residual: {np.max(magnitudes):.2f}px (Vector Scale: {scale}x)",
        (50, 50),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (255, 255, 255),
        2,
    )

    cv2.imwrite(output_file, img)
    print(f"Visualization saved to {output_file}")


if __name__ == "__main__":
    visualize_distortion()
