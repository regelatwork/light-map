import json
import os
import cv2
import numpy as np
from light_map.token_tracker import TokenTracker
from light_map.map_system import MapSystem

# Path to samples
SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "../samples")
SAMPLE_JSON = os.path.join(SAMPLES_DIR, "token_capture_20260211_235147_L255.json")


def load_sample_data():
    with open(SAMPLE_JSON, "r") as f:
        data = json.load(f)

    image_path = os.path.join(SAMPLES_DIR, data["image_file"])
    image = cv2.imread(image_path)

    return image, data


def test_token_tracker_offline_detection():
    # 1. Load Data
    image, metadata = load_sample_data()
    assert image is not None, "Failed to load sample image"

    config = metadata["config"]
    viewport = config["viewport"]
    projector_matrix = np.array(config["projector_matrix"])
    grid_spacing = config["grid_spacing_svg"]
    grid_origin_x = config.get("grid_origin_svg_x", 0.0)
    grid_origin_y = config.get("grid_origin_svg_y", 0.0)

    # 2. Setup MapSystem
    h, w = image.shape[:2]
    from light_map.common_types import AppConfig

    app_config = AppConfig(width=w, height=h, projector_matrix=np.eye(3))
    map_system = MapSystem(app_config)

    # Set State
    map_system.set_state(
        x=viewport["x"],
        y=viewport["y"],
        zoom=viewport["zoom"],
        rotation=viewport["rotation"],
    )

    # 3. Run Tracker
    tracker = TokenTracker()

    tokens = tracker.detect_tokens(
        frame_white=image,
        projector_matrix=projector_matrix,
        map_system=map_system,
        grid_spacing_svg=grid_spacing,
        grid_origin_x=grid_origin_x,
        grid_origin_y=grid_origin_y,
        mask_rois=[(0, 0, w, 150)],
        ppi=config.get("projector_ppi", 0.0),
    )

    # 4. Assertions
    expected = metadata["expected_tokens"]
    print(f"\nDetected {len(tokens)} tokens (Expected {len(expected)}):")
    for t in tokens:
        print(
            f"  Token {t.id}: World({t.world_x:.1f}, {t.world_y:.1f}) -> Grid({t.grid_x}, {t.grid_y})"
        )

    found_count = 0
    # We match by grid coordinates with a small tolerance if needed,
    # but since we snapped, we can match exactly.

    for exp in expected:
        # Simple list filtering to properly count matches
        if exp["grid_x"] is not None:
            candidates = [
                t
                for t in tokens
                if t.grid_x == exp["grid_x"] and t.grid_y == exp["grid_y"]
            ]
            if candidates:
                found_count += 1
                # Remove from pool to avoid double count if duplicates exist (unlikely for grid)
                tokens.remove(candidates[0])
                print(f"  [OK] Found Grid({exp['grid_x']}, {exp['grid_y']})")
            else:
                print(f"  [FAIL] Missing Grid({exp['grid_x']}, {exp['grid_y']})")
        else:
            candidates = [t for t in tokens if t.grid_x is None]
            if candidates:
                found_count += 1
                tokens.remove(candidates[0])
                print("  [OK] Found Unsnapped Token")
            else:
                print("  [FAIL] Missing Unsnapped Token")

    assert found_count == len(expected), (
        f"Expected {len(expected)} tokens, found {found_count}"
    )


if __name__ == "__main__":
    test_token_tracker_offline_detection()
