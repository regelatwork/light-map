import numpy as np
from light_map.vision.processing.hand_masker import HandMasker
from light_map.core.common_types import GmPosition


def test_is_point_masked_inside_always_allowed():
    masker = HandMasker()
    resolution = (1000, 1000)

    # All interior points should be False (not masked) regardless of GmPosition
    positions = [
        GmPosition.NONE,
        GmPosition.NORTH,
        GmPosition.SOUTH,
        GmPosition.NORTH_WEST,
        GmPosition.SOUTH_EAST,
    ]

    for pos in positions:
        # Center
        assert not masker.is_point_masked(500, 500, pos, resolution)
        # Corners
        assert not masker.is_point_masked(0, 0, pos, resolution)
        assert not masker.is_point_masked(999, 999, pos, resolution)


def test_is_point_masked_outside_none():
    masker = HandMasker()
    resolution = (1000, 1000)
    # If NONE, everything outside is masked
    assert masker.is_point_masked(-10, 500, GmPosition.NONE, resolution)
    assert masker.is_point_masked(1010, 500, GmPosition.NONE, resolution)
    assert masker.is_point_masked(500, -10, GmPosition.NONE, resolution)
    assert masker.is_point_masked(500, 1010, GmPosition.NONE, resolution)


def test_is_point_masked_outside_smart():
    masker = HandMasker()
    resolution = (1000, 1000)

    # NORTH allows points with y < 0
    assert not masker.is_point_masked(500, -10, GmPosition.NORTH, resolution)
    assert masker.is_point_masked(500, 1010, GmPosition.NORTH, resolution)
    assert masker.is_point_masked(-10, 500, GmPosition.NORTH, resolution)

    # SOUTH allows points with y >= 1000
    assert not masker.is_point_masked(500, 1010, GmPosition.SOUTH, resolution)
    assert masker.is_point_masked(500, -10, GmPosition.SOUTH, resolution)

    # NORTH_WEST allows points with y < 0 OR x < 0
    assert not masker.is_point_masked(-10, 500, GmPosition.NORTH_WEST, resolution)
    assert not masker.is_point_masked(500, -10, GmPosition.NORTH_WEST, resolution)
    assert not masker.is_point_masked(-10, -10, GmPosition.NORTH_WEST, resolution)
    assert masker.is_point_masked(1010, 500, GmPosition.NORTH_WEST, resolution)
    assert masker.is_point_masked(500, 1010, GmPosition.NORTH_WEST, resolution)


def test_generate_mask_image():
    masker = HandMasker()
    width, height = 100, 100

    # Create a simple hull (a square in the middle)
    hulls = [np.array([[40, 40], [60, 40], [60, 60], [40, 60]], dtype=np.int32)]

    mask = masker.generate_mask_image(hulls, width, height, blur=0)

    assert mask.shape == (height, width)
    assert mask[50, 50] == 255  # Inside the square
    assert mask[10, 10] == 0  # Outside


def test_compute_hulls_from_landmarks():
    masker = HandMasker()

    # Mock landmarks
    class MockLandmark:
        def __init__(self, x, y):
            self.x = x
            self.y = y

    class MockLandmarks:
        def __init__(self, pts):
            self.landmark = [MockLandmark(p[0], p[1]) for p in pts]

    landmarks = MockLandmarks([(0.1, 0.1), (0.2, 0.1), (0.2, 0.2), (0.1, 0.2)])

    # Transformation function: just scale by 1000
    def transform(pts):
        return pts * 1000

    hulls = masker.compute_hulls([landmarks], transform, current_time=0.0)

    assert len(hulls) == 1
    assert hulls[0].shape[0] >= 3  # Should be a polygon
    # Check if points are roughly 100, 100, etc.
    assert np.any(np.all(np.isclose(hulls[0], [100, 100], atol=1), axis=1))


def test_persistence_default():
    # New default is 1.0 seconds
    masker = HandMasker()

    landmarks = [
        {"x": 0.1, "y": 0.1},
        {"x": 0.2, "y": 0.2},
        {"x": 0.3, "y": 0.1},
    ]

    def transform(pts):
        return pts * 1000

    # Frame 1: Detection at t=0
    hulls1 = masker.compute_hulls([landmarks], transform, current_time=0.0)
    assert len(hulls1) == 1

    # Frame 2: Lost detection at t=0.5
    hulls2 = masker.compute_hulls([], transform, current_time=0.5)
    assert len(hulls2) == 1  # Persisted within 1s
    assert np.array_equal(hulls2[0], hulls1[0])

    # Frame 3: Still lost at t=1.1
    hulls3 = masker.compute_hulls([], transform, current_time=1.1)
    assert len(hulls3) == 0  # Now empty after 1.1s


def test_persistence_manual():
    # Verify it still works if manually set to different duration
    masker = HandMasker(persistence_seconds=2.0)
    landmarks = [
        {"x": 0.1, "y": 0.1},
        {"x": 0.2, "y": 0.2},
        {"x": 0.3, "y": 0.1},
    ]

    def transform(pts):
        return pts * 1000

    # Frame 1: Detection at t=0
    hulls1 = masker.compute_hulls([landmarks], transform, current_time=0.0)
    assert len(hulls1) == 1

    # Frame 2: Lost detection at t=1.5
    hulls2 = masker.compute_hulls([], transform, current_time=1.5)
    assert len(hulls2) == 1  # Persisted (within 2s)

    # Frame 3: Lost at t=2.1
    hulls3 = masker.compute_hulls([], transform, current_time=2.1)
    assert len(hulls3) == 0  # Now empty after 2.1s


def test_get_mask_hulls():
    masker = HandMasker()
    # Mock landmarks (normalized 0-1)
    hands = [[{"x": 0.1, "y": 0.1}, {"x": 0.2, "y": 0.1}, {"x": 0.2, "y": 0.2}]]

    # Mock transformation function (scale by 1000)
    def transform(pts):
        return pts * 1000

    hulls = masker.get_mask_hulls(hands, transform, current_time=1.0)

    assert len(hulls) == 1
    # Check that points are in projector space (around 100, 100)
    assert np.any(np.all(np.isclose(hulls[0], [100, 100], atol=1), axis=1))
