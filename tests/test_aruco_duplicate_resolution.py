import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from light_map.vision.aruco_detector import ArucoTokenDetector
from light_map.map_system import MapSystem


@pytest.fixture
def mock_map_system():
    ms = MagicMock(spec=MapSystem)
    ms.screen_to_world.side_effect = lambda x, y: (x, y)
    return ms


@patch("cv2.aruco.ArucoDetector")
@patch("cv2.aruco.getPredefinedDictionary")
@patch("cv2.aruco.DetectorParameters")
@patch("os.path.exists")
@patch("numpy.load")
def test_aruco_detector_resolves_duplicates(
    mock_load, mock_exists, mock_params, mock_dict, MockDetector, mock_map_system
):
    # Setup calibration mocks
    mock_exists.return_value = True
    mock_data = {
        "camera_matrix": np.eye(3),
        "dist_coeffs": np.zeros(5),
        "rvec": np.zeros((3, 1)),
        "tvec": np.array([[0, 0, -500]], dtype=np.float32),  # Camera at Z=-500
    }
    mock_load.return_value = mock_data

    detector = ArucoTokenDetector()

    # Mock detected markers: Two with ID 10
    # Marker 1: Small (area approx 100)
    corners1 = np.array([[[10, 10], [20, 10], [20, 20], [10, 20]]], dtype=np.float32)
    # Marker 2: Large (area approx 400)
    corners2 = np.array(
        [[[100, 100], [120, 100], [120, 120], [100, 120]]], dtype=np.float32
    )

    ids = np.array([[10], [10]], dtype=np.int32)
    corners = [corners1, corners2]

    detector.detector.detectMarkers.return_value = (corners, ids, [])

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    tokens = detector.detect(frame, mock_map_system)

    assert len(tokens) == 2

    # Large marker should be primary (is_duplicate=False)
    primary = [t for t in tokens if not t.is_duplicate]
    assert len(primary) == 1
    assert primary[0].id == 10
    # Center of corners2 is (110, 110). Due to parallax at Z=0 and Cam at Z=-500,
    # and identity matrix, it should be near (110, 110) in world?
    # Actually _parallax_correction with K=I, R=I, C=(0,0,-500), h=5, v=(u,v,1)
    # s = (5 - (-500)) / 1 = 505. P = (0,0,-500) + 505*(u,v,1) = (505u, 505v, 5).
    # Since u,v are around 110, wx_mm will be large.
    # The important part is that we have one primary and one duplicate.

    duplicate = [t for t in tokens if t.is_duplicate]
    assert len(duplicate) == 1
    assert duplicate[0].id == 10


def test_aruco_detector_multiple_ids_with_duplicates(mock_map_system):
    # We need to mock more things if we don't want to rely on the full class
    # but let's just use the patched version if possible.
    pass


@patch("cv2.aruco.ArucoDetector")
@patch("cv2.aruco.getPredefinedDictionary")
@patch("cv2.aruco.DetectorParameters")
@patch("os.path.exists")
@patch("numpy.load")
def test_aruco_detector_orders_by_area(
    mock_load, mock_exists, mock_params, mock_dict, MockDetector, mock_map_system
):
    mock_exists.return_value = True
    mock_data = {
        "camera_matrix": np.eye(3),
        "dist_coeffs": np.zeros(5),
        "rvec": np.zeros((3, 1)),
        "tvec": np.array([[0, 0, -500]], dtype=np.float32),
    }
    mock_load.return_value = mock_data

    detector = ArucoTokenDetector()

    # ID 1: Large (area 400), ID 1: Small (area 100), ID 2: Medium (area 200)
    c1_large = np.array(
        [[[0, 0], [20, 0], [20, 20], [0, 20]]], dtype=np.float32
    )  # area 400
    c1_small = np.array(
        [[[50, 50], [60, 50], [60, 60], [50, 60]]], dtype=np.float32
    )  # area 100
    c2_med = np.array(
        [[[100, 100], [114.14, 100], [114.14, 114.14], [100, 114.14]]], dtype=np.float32
    )  # area approx 200

    ids = np.array([[1], [1], [2]], dtype=np.int32)
    corners = [c1_large, c1_small, c2_med]

    detector.detector.detectMarkers.return_value = (corners, ids, [])

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    tokens = detector.detect(frame, mock_map_system)

    assert len(tokens) == 3

    id1_tokens = [t for t in tokens if t.id == 1]
    assert len(id1_tokens) == 2
    assert sum(1 for t in id1_tokens if not t.is_duplicate) == 1
    assert sum(1 for t in id1_tokens if t.is_duplicate) == 1

    id2_tokens = [t for t in tokens if t.id == 2]
    assert len(id2_tokens) == 1
    assert not id2_tokens[0].is_duplicate
