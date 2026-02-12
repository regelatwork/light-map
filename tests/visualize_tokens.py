import json
import os
import cv2
import numpy as np
from light_map.map_system import MapSystem

# Path to samples
SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "../samples")
SAMPLE_JSON = os.path.join(SAMPLES_DIR, "token_capture_20260211_235147_L255.json")
OUTPUT_FILE = os.path.join(SAMPLES_DIR, "debug/token_overlay_labeled.png")

def generate_labeled_overlay():
    # 1. Load Data
    with open(SAMPLE_JSON, "r") as f:
        metadata = json.load(f)
    
    image_path = os.path.join(SAMPLES_DIR, metadata["image_file"])
    frame = cv2.imread(image_path)
    assert frame is not None, "Failed to load sample image"
    
    config = metadata["config"]
    projector_matrix = np.array(config["projector_matrix"])
    grid_spacing = config["grid_spacing_svg"]
    
    # Map System for coordinate conversion (to show Grid Coords)
    h, w = frame.shape[:2]
    map_system = MapSystem(w, h)
    viewport = config["viewport"]
    map_system.set_state(viewport["x"], viewport["y"], viewport["zoom"], viewport["rotation"])

    # 2. Pipeline (Replicating TokenTracker logic)
    # Warp
    warped = cv2.warpPerspective(frame, projector_matrix, (w, h))
    
    # Mask out UI text (Top Strip)
    # Masking full width to avoid any text issues, height 150.
    cv2.rectangle(warped, (0, 0), (w, 150), (255, 255, 255), -1)

    gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
    
    # Adaptive Threshold
    gray = cv2.GaussianBlur(gray, (9, 9), 2)
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 101, 10
    )
    
    # Morph
    kernel_open = np.ones((3, 3), np.uint8)
    opening = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel_open, iterations=2)
    kernel_close = np.ones((7, 7), np.uint8)
    closing = cv2.morphologyEx(opening, cv2.MORPH_CLOSE, kernel_close, iterations=3)
    
    # Distance Transform & Sure FG
    sure_bg = cv2.dilate(closing, kernel_open, iterations=3)
    dist_transform = cv2.distanceTransform(closing, cv2.DIST_L2, 5)
    _, sure_fg = cv2.threshold(dist_transform, 10.0, 255, 0)
    sure_fg = np.uint8(sure_fg)
    unknown = cv2.subtract(sure_bg, sure_fg)
    
    # Watershed Markers
    ret, markers = cv2.connectedComponents(sure_fg)
    markers = markers + 1
    markers[unknown == 255] = 0
    markers = cv2.watershed(warped, markers)
    
    # 3. Visualization
    # Create a clean canvas or use warped image
    vis = warped.copy()
    
    unique_markers = np.unique(markers)
    token_id = 1
    
    print(f"Generating visualization for {len(unique_markers)-2} potential blobs...")
    
    for marker_id in unique_markers:
        if marker_id <= 1: # Skip background/unknown
            continue
            
        # Create mask for this marker
        mask = np.zeros_like(gray, dtype=np.uint8)
        mask[markers == marker_id] = 255
        
        # Area Filter (Match TokenTracker)
        area = cv2.countNonZero(mask)
        if area < 300:
            continue
            
        # Find Contours for outline
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Calculate Centroid
        M = cv2.moments(mask)
        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            
            # Get Grid Coords
            wx, wy = map_system.screen_to_world(cx, cy)
            gx = round(wx / grid_spacing)
            gy = round(wy / grid_spacing)
            
            # Check snap distance
            snapped_wx = gx * grid_spacing
            snapped_wy = gy * grid_spacing
            dist = np.sqrt((wx - snapped_wx)**2 + (wy - snapped_wy)**2)
            is_snapped = dist < (0.4 * grid_spacing)
            
            label = f"#{token_id}"
            sub_label = f"({gx},{gy})" if is_snapped else "(?,?)"
            
            # Draw Outline
            color = (0, 255, 0) if is_snapped else (0, 165, 255) # Green if snapped, Orange if not
            cv2.drawContours(vis, contours, -1, color, 2)
            
            # Draw Label
            cv2.putText(vis, label, (cx - 10, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            cv2.putText(vis, sub_label, (cx - 20, cy + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 0), 1)
            
            token_id += 1

    # Save
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    cv2.imwrite(OUTPUT_FILE, vis)
    print(f"Visualization saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    generate_labeled_overlay()
