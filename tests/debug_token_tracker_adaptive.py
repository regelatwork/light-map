import json
import os
import cv2
import numpy as np
from light_map.token_tracker import TokenTracker

# Path to samples
SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "../samples")
SAMPLE_JSON = os.path.join(SAMPLES_DIR, "token_capture_20260211_235147_L255.json")

def debug_token_tracker_adaptive():
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
    warped = cv2.warpPerspective(frame, projector_matrix, (w, h))
    gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
    
    # 3. Adaptive Threshold
    # block_size: 11 (must be odd), C: 2 (constant subtracted from mean)
    # Using larger block size (e.g. 51, 101) handles larger shadows better.
    # Tokens are roughly 50px wide. Block size should be larger than token size?
    # Let's try 101.
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                   cv2.THRESH_BINARY_INV, 101, 10)
    
    cv2.imwrite("samples/debug/step2_adaptive.png", thresh)
    
    # 4. Morphological Ops (Cleaning)
    kernel = np.ones((3, 3), np.uint8)
    opening = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=2)
    # Closing to fill holes inside tokens
    closing = cv2.morphologyEx(opening, cv2.MORPH_CLOSE, kernel, iterations=2)
    
    cv2.imwrite("samples/debug/step3_morph.png", closing)

    # 5. Simple Contour Finding (Debug Step)
    contours, _ = cv2.findContours(closing, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    print(f"Total contours found: {len(contours)}")
    
    # Filter by Area
    min_area = 500   # ~0.5 inch diameter
    max_area = 10000 # ~2 inch diameter
    
    valid_contours = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if min_area < area < max_area:
            valid_contours.append(cnt)
        else:
            # Draw rejected contours in red
            pass
            
    print(f"Valid contours (Area {min_area}-{max_area}): {len(valid_contours)}")
    
    # 6. Visualization
    vis = warped.copy()
    cv2.drawContours(vis, valid_contours, -1, (0, 255, 0), 2)
    cv2.imwrite("samples/debug/step6_adaptive_result.png", vis)
    
    # Print areas of valid contours
    for i, cnt in enumerate(valid_contours):
        M = cv2.moments(cnt)
        cx = int(M["m10"] / M["m00"]) if M["m00"] != 0 else 0
        cy = int(M["m01"] / M["m00"]) if M["m00"] != 0 else 0
        print(f"  Contour {i}: Area={cv2.contourArea(cnt):.0f} at ({cx}, {cy})")

if __name__ == "__main__":
    debug_token_tracker_adaptive()
