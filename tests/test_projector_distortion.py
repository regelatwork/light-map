import numpy as np
from light_map.projector import ProjectorDistortionModel


def test_projector_distortion_model_interpolation():
    # Setup a simple 2x2 grid of projector points
    # Px = [100, 200], Py = [100, 200]
    proj_pts = np.array(
        [[100, 100], [200, 100], [100, 200], [200, 200]], dtype=np.float32
    )

    # Matching camera points (identity-ish)
    cam_pts = np.array([[10, 10], [20, 10], [10, 20], [20, 20]], dtype=np.float32)

    # Identity homography (simplified)
    # Mapping [10, 10] to [100, 100] etc.
    # Scale = 10
    homography = np.array([[10, 0, 0], [0, 10, 0], [0, 0, 1]], dtype=np.float32)

    # 1. Test with zero residuals
    model = ProjectorDistortionModel(homography, cam_pts, proj_pts)
    assert np.allclose(model.grid_residuals, 0)

    # Apply correction to a point in the center [15, 15] -> [150, 150]
    pt_cam = np.array([[15, 15]], dtype=np.float32)
    pt_corr = model.apply_correction(pt_cam)
    assert np.allclose(pt_corr.flatten(), [150, 150])


def test_projector_distortion_model_with_residuals():
    # Setup 2x2 grid
    cam_pts = np.array([[10, 10], [20, 10], [10, 20], [20, 20]], dtype=np.float32)

    homography = np.array([[10, 0, 0], [0, 10, 0], [0, 0, 1]], dtype=np.float32)

    # Manually modify proj_pts to introduce residuals
    # [100, 100] -> [105, 105] (Residual +5, +5)
    # [200, 100] -> [195, 105] (Residual -5, +5)
    # [100, 200] -> [105, 195] (Residual +5, -5)
    # [200, 200] -> [195, 195] (Residual -5, -5)
    proj_pts_distorted = np.array(
        [[105, 105], [195, 105], [105, 195], [195, 195]], dtype=np.float32
    )

    model = ProjectorDistortionModel(homography, cam_pts, proj_pts_distorted)

    # Check residuals at corners
    assert np.allclose(model.grid_residuals[0, 0], [5, 5])
    assert np.allclose(model.grid_residuals[0, 1], [-5, 5])

    # Interp at center [150, 150] should have 0 residual (linear cancelation)
    # tx = 0.5, ty = 0.5
    # r00*(0.5*0.5) + r10*(0.5*0.5) + r01*(0.5*0.5) + r11*(0.5*0.5)
    # (5,5)*0.25 + (-5,5)*0.25 + (5,-5)*0.25 + (-5,-5)*0.25 = (0,0)
    rx, ry = model._interpolate_residual(150, 150)
    assert np.allclose([rx, ry], [0, 0])

    # Interp at [150, 105] (Top edge, near middle)
    # unique_proj_x = [105, 195]. px = 150.
    # tx = (150 - 105) / (195 - 105) = 45 / 90 = 0.5
    # r00*(0.5) + r10*(0.5)
    # (5,5)*0.5 + (-5,5)*0.5 = (2.5 - 2.5, 2.5 + 2.5) = (0, 5)
    rx, ry = model._interpolate_residual(150, 105)
    assert np.allclose([rx, ry], [0, 5])


def test_projector_distortion_model_clamping():
    proj_pts = np.array(
        [[100, 100], [200, 100], [100, 200], [200, 200]], dtype=np.float32
    )
    cam_pts = np.array([[10, 10], [20, 10], [10, 20], [20, 20]], dtype=np.float32)
    homography = np.eye(3) * 10
    homography[2, 2] = 1

    proj_pts_distorted = proj_pts + 10  # Constant +10 offset
    model = ProjectorDistortionModel(homography, cam_pts, proj_pts_distorted)

    # Out of bounds [50, 50] should clamp to [100, 100] residual
    rx, ry = model._interpolate_residual(50, 50)
    assert np.allclose([rx, ry], [10, 10])

    # Out of bounds [250, 250] should clamp to [200, 200] residual
    rx, ry = model._interpolate_residual(250, 250)
    assert np.allclose([rx, ry], [10, 10])


def test_projector_distortion_empty_input():
    # Just to cover the empty check
    model = ProjectorDistortionModel(
        np.eye(3),
        np.zeros((4, 2), dtype=np.float32),
        np.zeros((4, 2), dtype=np.float32),
    )
    res = model.apply_correction(np.array([], dtype=np.float32))
    assert res.size == 0
