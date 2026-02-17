import numpy as np
import pytest
import cv2
from unittest.mock import MagicMock
from light_map.token_tracker import TokenTracker, TokenDetectionAlgorithm
from light_map.map_system import MapSystem
from light_map.common_types import Token

@pytest.fixture
def tracker():
    return TokenTracker()

@pytest.fixture
def map_system():
    ms = MagicMock(spec=MapSystem)
    # Mock screen_to_world to be identity for simplicity
    ms.screen_to_world.side_effect = lambda x, y: (float(x), float(y))
    ms.world_to_screen.side_effect = lambda x, y: (x, y)
    return ms

def test_get_scan_pattern_shape(tracker):
    width, height = 640, 480
    ppi = 96.0
    img, points = tracker.get_scan_pattern(width, height, ppi)
    
    assert img.shape == (height, width, 3)
    assert len(points) > 0
    # Approx spacing is 96 * 0.4 = 38.4 -> 38 pixels
    # Grid size approx (640/38) * (480/38) = 16 * 12 = 192 points
    assert 100 < len(points) < 300

def test_detect_structured_light_no_shift(tracker, map_system):
    width, height = 640, 480
    ppi = 96.0
    
    # 1. Generate Pattern
    import random
    random.seed(42)
    pattern_img, expected_points = tracker.get_scan_pattern(width, height, ppi)
    
    # 2. Assume Projector Matrix is Identity (Camera sees exactly what is projected)
    projector_matrix = np.eye(3, dtype=np.float32)
    
    # 3. Dark Frame is black
    frame_dark = np.zeros((height, width, 3), dtype=np.uint8)
    
    # 4. Pattern Frame is perfectly aligned (Projected = Captured)
    frame_pattern = pattern_img.copy()
    
    # 5. Run Detection
    # Note: We need to ensure we use the SAME points.
    # tracker.detect_tokens re-generates points using seed 42.
    # So we strictly rely on that behavior.
    
    tokens = tracker.detect_tokens(
        frame_pattern=frame_pattern,
        projector_matrix=projector_matrix,
        map_system=map_system,
        frame_dark=frame_dark,
        ppi=ppi,
        algorithm=TokenDetectionAlgorithm.STRUCTURED_LIGHT
    )
    
    # Should detect 0 tokens because all points match expected locations
    assert len(tokens) == 0

def test_detect_structured_light_with_shift(tracker, map_system):
    width, height = 640, 480
    ppi = 96.0
    
    # 1. Generate Pattern internally (we rely on deterministic seed 42 inside detect_tokens)
    # To modify the frame, we need to know where the points ARE.
    # So we call it manually with same seed.
    import random
    random.seed(42)
    pattern_img, expected_points = tracker.get_scan_pattern(width, height, ppi)
    
    frame_pattern = pattern_img.copy()
    
    # 2. Modify one point to be shifted
    # Pick a point in the middle
    idx = len(expected_points) // 2
    ex, ey = expected_points[idx]
    
    # Erase original point
    cv2.circle(frame_pattern, (ex, ey), 5, (0, 0, 0), -1)
    
    # Draw shifted point (shift by 10 pixels, threshold is 3.0)
    sx, sy = ex + 10, ey + 10
    cv2.circle(frame_pattern, (sx, sy), 3, (255, 255, 255), -1)
    
    # 3. Setup
    projector_matrix = np.eye(3, dtype=np.float32)
    frame_dark = np.zeros((height, width, 3), dtype=np.uint8)
    
    # 4. Run Detection
    tokens = tracker.detect_tokens(
        frame_pattern=frame_pattern,
        projector_matrix=projector_matrix,
        map_system=map_system,
        frame_dark=frame_dark,
        ppi=ppi,
        algorithm=TokenDetectionAlgorithm.STRUCTURED_LIGHT
    )
    
    # 5. Verify
    # Should detect 1 token (or maybe 0 depending on cluster size threshold)
    # Ref: logic says "if len(cluster) < 2: continue"??
    # Wait, my implementation said: `if len(cluster) < 2: continue`.
    # So a single point shift will be ignored as noise!
    # I should shift 2 points close to each other.
    
    assert len(tokens) == 0 # Because of cluster size < 2 check


def test_detect_structured_light_with_cluster_shift(tracker, map_system):
    width, height = 640, 480
    ppi = 96.0
    
    import random
    random.seed(42)
    pattern_img, expected_points = tracker.get_scan_pattern(width, height, ppi)
    
    frame_pattern = pattern_img.copy()
    
    # Shift 2 adjacent points to form a cluster
    # Find two points close to center
    cx, cy = width // 2, height // 2
    # simple search
    sorted_pts = sorted(expected_points, key=lambda p: (p[0]-cx)**2 + (p[1]-cy)**2)
    p1 = sorted_pts[0]
    p2 = sorted_pts[1]
    
    # Erase originals
    cv2.circle(frame_pattern, p1, 5, (0, 0, 0), -1)
    cv2.circle(frame_pattern, p2, 5, (0, 0, 0), -1)
    
    # Draw shifted points
    # Shift them both by (10, 10). They will remain adjacent relative to each other.
    s1 = (p1[0] + 10, p1[1] + 10)
    s2 = (p2[0] + 10, p2[1] + 10)
    
    cv2.circle(frame_pattern, s1, 3, (255, 255, 255), -1)
    cv2.circle(frame_pattern, s2, 3, (255, 255, 255), -1)
    
    projector_matrix = np.eye(3, dtype=np.float32)
    frame_dark = np.zeros((height, width, 3), dtype=np.uint8)
    
    tokens = tracker.detect_tokens(
        frame_pattern=frame_pattern,
        projector_matrix=projector_matrix,
        map_system=map_system,
        frame_dark=frame_dark,
        ppi=ppi,
        algorithm=TokenDetectionAlgorithm.STRUCTURED_LIGHT
    )
    
    assert len(tokens) == 1
    # Check position approx match centroid of shifted points
    tx, ty = tokens[0].world_x, tokens[0].world_y
    expected_x = (s1[0] + s2[0]) / 2.0
    expected_y = (s1[1] + s2[1]) / 2.0
    
    assert abs(tx - expected_x) < 2.0
    assert abs(ty - expected_y) < 2.0
