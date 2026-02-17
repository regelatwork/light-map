import numpy as np
import pytest
import cv2
from unittest.mock import MagicMock
from light_map.token_tracker import TokenTracker, TokenDetectionAlgorithm
from light_map.map_system import MapSystem


@pytest.fixture
def tracker():
    return TokenTracker()


@pytest.fixture
def map_system():
    ms = MagicMock(spec=MapSystem)
    # Mock screen_to_world to be identity for simplicity
    ms.screen_to_world.side_effect = lambda x, y: (float(x), float(y))
    ms.world_to_screen.side_effect = lambda x, y: (x, y)
    ms.width = 640
    ms.height = 480
    return ms


def test_get_scan_pattern_shape(tracker):
    width, height = 640, 480
    ppi = 96.0
    img, points = tracker.get_scan_pattern(width, height, ppi)

    assert img.shape == (height, width, 3)
    assert len(points) > 0
    # Approx spacing is 96 * 0.8 = 76 pixels (sparser grid)
    # Grid size approx (640/76) * (480/76) = 8.4 * 6.3 = ~53 points
    # Range should be lower
    assert 40 <= len(points) <= 100


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
    tokens = tracker.detect_tokens(
        frame_pattern=frame_pattern,
        projector_matrix=projector_matrix,
        map_system=map_system,
        frame_dark=frame_dark,
        ppi=ppi,
        algorithm=TokenDetectionAlgorithm.STRUCTURED_LIGHT,
    )

    # Should detect 0 tokens because all points match expected locations
    assert len(tokens) == 0


def test_detect_structured_light_with_shift(tracker, map_system):
    width, height = 640, 480
    ppi = 96.0

    # 1. Generate Pattern internally (we rely on deterministic seed 42 inside detect_tokens)
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

    # Draw shifted point (shift by 25 pixels, threshold is 15.0)
    sx, sy = ex + 25, ey + 25
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
        algorithm=TokenDetectionAlgorithm.STRUCTURED_LIGHT,
    )

    # 5. Verify
    # Should detect 1 token because cluster size >= 1
    assert len(tokens) == 1


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
    sorted_pts = sorted(
        expected_points, key=lambda p: (p[0] - cx) ** 2 + (p[1] - cy) ** 2
    )
    p1 = sorted_pts[0]
    p2 = sorted_pts[1]

    # Erase originals
    cv2.circle(frame_pattern, p1, 5, (0, 0, 0), -1)
    cv2.circle(frame_pattern, p2, 5, (0, 0, 0), -1)

    # Draw shifted points
    # Shift them both by (20, 20). Distance = sqrt(20^2 + 20^2) = 28px > 15px.
    s1 = (p1[0] + 20, p1[1] + 20)
    s2 = (p2[0] + 20, p2[1] + 20)

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
        algorithm=TokenDetectionAlgorithm.STRUCTURED_LIGHT,
    )

    assert len(tokens) == 1
    # Check position matches centroid of BOTH shifted and missing points
    tx, ty = tokens[0].world_x, tokens[0].world_y
    # Shifted: s1, s2. Missing: p1, p2.
    expected_x = (s1[0] + s2[0] + p1[0] + p2[0]) / 4.0
    expected_y = (s1[1] + s2[1] + p1[1] + p2[1]) / 4.0

    assert abs(tx - expected_x) < 2.0
    assert abs(ty - expected_y) < 2.0
