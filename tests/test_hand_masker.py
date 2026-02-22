import numpy as np
from light_map.vision.hand_masker import HandMasker
from light_map.common_types import GmPosition


def test_is_point_masked_none():
    masker = HandMasker()
    # If GmPosition.NONE, nothing should be masked
    assert not masker.is_point_masked(100, 100, GmPosition.NONE, (1000, 1000))


def test_is_point_masked_north():
    masker = HandMasker()
    resolution = (1000, 1000)

    # North: Unmasked if y < 500
    assert not masker.is_point_masked(500, 200, GmPosition.NORTH, resolution)
    assert masker.is_point_masked(500, 800, GmPosition.NORTH, resolution)

    # South: Unmasked if y > 500
    assert not masker.is_point_masked(500, 800, GmPosition.SOUTH, resolution)
    assert masker.is_point_masked(500, 200, GmPosition.SOUTH, resolution)

    # West: Unmasked if x < 500
    assert not masker.is_point_masked(200, 500, GmPosition.WEST, resolution)
    assert masker.is_point_masked(800, 500, GmPosition.WEST, resolution)

    # East: Unmasked if x > 500
    assert not masker.is_point_masked(800, 500, GmPosition.EAST, resolution)
    assert masker.is_point_masked(200, 500, GmPosition.EAST, resolution)


def test_is_point_masked_diagonal():
    masker = HandMasker()
    resolution = (1000, 1000)

    # North West: Unmasked if x < 500 AND y < 500
    assert not masker.is_point_masked(200, 200, GmPosition.NORTH_WEST, resolution)
    assert masker.is_point_masked(800, 200, GmPosition.NORTH_WEST, resolution)
    assert masker.is_point_masked(200, 800, GmPosition.NORTH_WEST, resolution)
    assert masker.is_point_masked(800, 800, GmPosition.NORTH_WEST, resolution)


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

    hulls = masker.compute_hulls([landmarks], transform, padding=0)

    assert len(hulls) == 1
    assert hulls[0].shape[0] >= 3  # Should be a polygon
    # Check if points are roughly 100, 100, etc.
    assert np.any(np.all(np.isclose(hulls[0], [100, 100], atol=1), axis=1))


def test_persistence():
    masker = HandMasker(persistence_frames=2)

    # Mock landmarks
    class MockLandmark:
        def __init__(self, x, y):
            self.x = x
            self.y = y

    class MockLandmarks:
        def __init__(self, pts):
            self.landmark = [MockLandmark(p[0], p[1]) for p in pts]

    landmarks = MockLandmarks([(0.1, 0.1), (0.2, 0.2), (0.3, 0.1)])

    def transform(pts):
        return pts * 1000

    # Frame 1: Detection
    hulls1 = masker.compute_hulls([landmarks], transform)
    assert len(hulls1) == 1

    # Frame 2: Lost detection
    hulls2 = masker.compute_hulls([], transform)
    assert len(hulls2) == 1  # Persisted
    assert np.array_equal(hulls2[0], hulls1[0])

    # Frame 3: Still lost
    hulls3 = masker.compute_hulls([], transform)
    assert len(hulls3) == 1  # Still persisted

    # Frame 4: Exceeded persistence
    hulls4 = masker.compute_hulls([], transform)
    assert len(hulls4) == 0  # Now empty
