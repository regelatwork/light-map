import json
import os
import cv2
import numpy as np

# Path to samples
SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "../samples")
SAMPLE_JSON = os.path.join(SAMPLES_DIR, "token_capture_20260211_235147_L255.json")


def debug_token_tracker():
    # 1. Load Data
    with open(SAMPLE_JSON, "r") as f:
        metadata = json.load(f)

    image_path = os.path.join(SAMPLES_DIR, metadata["image_file"])
    frame = cv2.imread(image_path)
    assert frame is not None, "Failed to load sample image"

    config = metadata["config"]
    projector_matrix = np.array(config["projector_matrix"])
    h, w = frame.shape[:2]

    # 2. Warp
    # Use output size matching frame (assuming projector is same res)
    warped = cv2.warpPerspective(frame, projector_matrix, (w, h))
    cv2.imwrite("samples/debug/step1_warped.png", warped)

    # Analyze stats
    gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
    min_val, max_val, _, _ = cv2.minMaxLoc(gray)
    mean_val = np.mean(gray)
    print(f"Warped Stats: Min={min_val}, Max={max_val}, Mean={mean_val:.2f}")

    # 3. Threshold (Debug Values)
    # The user says "Flash Scan", so tokens are DARK on WHITE.
    # THRESH_BINARY_INV means:
    #   if pixel > thresh: output = 0 (Black) - Background
    #   if pixel <= thresh: output = 255 (White) - Foreground (Token)
    thresh_val = 200
    _, thresh = cv2.threshold(gray, thresh_val, 255, cv2.THRESH_BINARY_INV)
    cv2.imwrite("samples/debug/step2_thresh.png", thresh)

    print(f"Threshold used: {thresh_val}")
    print(f"Thresh non-zero (foreground) pixels: {cv2.countNonZero(thresh)}")

    # 4. Morphological Ops
    kernel = np.ones((3, 3), np.uint8)
    opening = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=2)
    cv2.imwrite("samples/debug/step3_opening.png", opening)

    # 5. Distance Transform
    dist_transform = cv2.distanceTransform(opening, cv2.DIST_L2, 5)
    print(f"Max Distance Transform Value: {dist_transform.max()}")
    # Normalize for saving
    dist_display = cv2.normalize(dist_transform, None, 0, 1.0, cv2.NORM_MINMAX) * 255
    dist_display = np.uint8(dist_display)
    cv2.imwrite("samples/debug/step4_dist_transform.png", dist_display)

    # Peak Finding (Sure Foreground)
    _, sure_fg = cv2.threshold(dist_transform, 0.5 * dist_transform.max(), 255, 0)
    sure_fg = np.uint8(sure_fg)
    cv2.imwrite("samples/debug/step5_sure_fg.png", sure_fg)

    print(f"Sure FG blobs found: {cv2.countNonZero(sure_fg)}")

    # 6. Watershed Markers
    sure_bg = cv2.dilate(opening, kernel, iterations=3)
    unknown = cv2.subtract(sure_bg, sure_fg)
    ret, markers = cv2.connectedComponents(sure_fg)
    markers = markers + 1
    markers[unknown == 255] = 0

    # Watershed
    markers = cv2.watershed(warped, markers)

    # Visualize Result
    vis = warped.copy()
    vis[markers == -1] = [0, 0, 255]  # Red boundaries

    # Count final tokens
    unique_markers = np.unique(markers)
    # Filter out 0 (unknown), 1 (background), -1 (boundary)
    valid_ids = [m for m in unique_markers if m > 1]

    print(f"Final Tokens Found: {len(valid_ids)}")

    # Color each token randomly
    for m_id in valid_ids:
        color = np.random.randint(0, 255, (3,)).tolist()
        vis[markers == m_id] = color

    cv2.imwrite("samples/debug/step6_result.png", vis)
    print("Debug images saved to samples/debug/")


if __name__ == "__main__":
    debug_token_tracker()
