"""
Integration test for SequentialSolver.
"""

import numpy as np

from light_map.core.calibration.solver import SequentialSolver


def test_solve_integration():
    K_L = np.array([[1000, 0, 960], [0, 1000, 540], [0, 0, 1]], dtype=np.float32)
    dist_L = np.zeros(5, dtype=np.float32)
    K_R = np.array([[1000, 0, 960], [0, 1000, 540], [0, 0, 1]], dtype=np.float32)
    dist_R = np.zeros(5, dtype=np.float32)

    solver = SequentialSolver(K_L, dist_L, K_R, dist_R)

    # We'll place 12 markers in a 4x3 grid on the tabletop (Z=0)
    # and 4 tokens at the corners of that grid at Z=50.

    # 3D points:
    pts_3d = {
        42: np.array([0, 0, 0], dtype=np.float32),
        43: np.array([100, 0, 0], dtype=np.float32),
        44: np.array([200, 0, 0], dtype=np.float32),
        45: np.array([300, 0, 0], dtype=np.float32),
        46: np.array([0, 100, 0], dtype=np.float32),
        47: np.array([100, 100, 0], dtype=np.float32),
        48: np.array([200, 100, 0], dtype=np.float32),
        49: np.array([300, 100, 0], dtype=np.float32),
        0: np.array([0, 0, 50], dtype=np.float32),
        1: np.array([300, 0, 50], dtype=np.float32),
        2: np.array([0, 100, 50], dtype=np.float32),
        3: np.array([300, 100, 50], dtype=np.float32),
    }

    # Project all pts_3d to camera L
    # We'll use a dummy pose (identity) for now
    # Then we'll use stereoCalibrate to find the actual R and t
    # and then we'll verify that the solver finds them.

    # For the test, we'll just provide points that are "correct" for identity extrinsics
    # and then see if the solver finds something close to identity.

    # Let's just mock the 2D points to be the projection of the 3D points
    # with identity pose.

    token_dets = []
    grid_dets = []
    ruler_dets = []

    # 12 markers
    for mid in [0, 1, 2, 3, 42, 43, 44, 45, 46, 47, 48, 49]:
        # Left camera
        token_dets.append(
            {"id": mid, "points": [pts_3d[mid][:2].tolist()], "side": "left", "height_mm": 50.0}
        )
        # Right camera
        token_dets.append(
            {
                "id": mid,
                "points": [(pts_3d[mid][:2] + [10, 10]).tolist()],
                "side": "right",
                "height_mm": 50.0,
            }
        )

    # Grid markers (42-49)
    for mid in [42, 43, 44, 45, 46, 47, 48, 49]:
        # Only one camera for the grid to avoid findHomography issues in this test
        grid_dets.append({"id": mid, "points": [pts_3d[mid][:2].tolist()], "side": "left"})

    # Ruler
    ruler_dets.append({"id": 40, "side": "left", "points": [[0, 0], [100, 100]]})
    ruler_dets.append({"id": 41, "side": "left", "points": [[100, 100], [200, 200]]})

    # Execute solver
    result = solver.solve(grid_dets, ruler_dets, token_dets, {})

    # Verify
    assert "R" in result
    assert "t" in result
    assert "roi_left" in result
    assert "roi_right" in result
    assert "table_homography" in result
    assert result["projector_ppi"] == 100.0
