import numpy as np
import cv2
import pytest
from light_map.vision.projection import (
    CameraProjectionModel,
    Projector3DModel,
    ProjectionService,
)


def test_projection_service_parallax_logic():
    # Setup: Camera at (0, 0, 1000) looking straight down (Z forward is World -Z)
    camera_matrix = np.array(
        [[1000, 0, 500], [0, 1000, 500], [0, 0, 1]], dtype=np.float32
    )
    dist_coeffs = np.zeros(5, dtype=np.float32)
    # Camera R: looking down. World Z+ is up. Camera Z+ is forward (down).
    # So Camera X=World X, Camera Y=World -Y, Camera Z=World -Z
    rotation_matrix = np.array([[1, 0, 0], [0, -1, 0], [0, 0, -1]], dtype=np.float32)
    rvec, _ = cv2.Rodrigues(rotation_matrix)
    tvec = np.array([[0], [0], [1000]], dtype=np.float32)

    camera_model = CameraProjectionModel(camera_matrix, dist_coeffs, rvec, tvec)

    # Setup: Projector at (200, 0, 1000) looking straight down (Offset by 200mm in X)
    proj_rvec = rvec.copy()
    # Actually translation_vector in projectPoints is T such that P_cam = R * P_world + T
    # So for world origin to be at (200, 0) in projector's view, T should be different.
    # Let's use the Projector3DModel's internal logic for projector_center.

    # Let's set the projector center directly by calculating the required translation
    # P_proj = -R^T * T  =>  T = -R * P_proj
    proj_center = np.array([200.0, 0.0, 1000.0])
    proj_tvec_fixed = -(rotation_matrix @ proj_center).reshape(3, 1)

    projector_model = Projector3DModel(
        intrinsic_matrix=camera_matrix.copy(),
        distortion_coefficients=dist_coeffs.copy(),
        rotation_vector=proj_rvec,
        translation_vector=proj_tvec_fixed,
        use_3d=True,
    )

    service = ProjectionService(camera_model, projector_model)

    # --- TEST 1: Object at (0, 0, 0), Target at (0, 0, 0) ---
    # Camera sees World(0,0,0) at pixel (500, 500)
    cam_pixels = np.array([[500, 500]], dtype=np.float32)
    proj_pixels = service.project_camera_to_projector(
        cam_pixels, height_mm=0, target_z=0, prefer_homography=False
    )

    # Projector at (200, 0, 1000) sees (0, 0, 0) at offset:
    # dx = -200, dz = -1000 => x_norm = -200/1000 = -0.2
    # pixel_x = 500 + (-0.2 * 1000) = 300
    assert proj_pixels[0, 0] == pytest.approx(300.0, abs=1e-2)
    assert proj_pixels[0, 1] == pytest.approx(500.0, abs=1e-2)

    # --- TEST 2: Object at (0, 0, 100), Target at (0, 0, 100) ---
    # To see World(0,0,100) at center, camera must be at (0,0)
    # But if camera is at (0,0,1000) and sees World(0,0,100), it's still pixel (500, 500)
    proj_pixels_h100 = service.project_camera_to_projector(
        cam_pixels, height_mm=100, target_z=100, prefer_homography=False
    )

    # Projector at (200, 0, 1000) sees World(0, 0, 100):
    # dx = -200, dz = -900 => x_norm = -200/900 = -0.222...
    # pixel_x = 500 + (-0.222 * 1000) = 277.77...
    assert proj_pixels_h100[0, 0] == pytest.approx(277.777, abs=1e-2)

    # Setup: Camera at (100, 0, 1000) looking at (0, 0, 0)
    # This creates an angled ray.
    # We'll use a simpler way: keep camera at (0,0,1000) but look at an offset pixel.

    # --- TEST 3: Object at (X, Y, 100), Target at (X, Y, 0) (Shadow) ---
    # Camera at (0,0,1000). Camera sees pixel (600, 500).
    # dx_norm = (600-500)/1000 = 0.1.
    # World Ray = [0.1, 0, -1]
    # At Z=100: [0,0,1000] + s*[0.1, 0, -1] = [x, y, 100] => s=900.
    # x = 90, y = 0.
    # So World Target is (90, 0, 100).
    cam_pixels_offset = np.array([[600, 500]], dtype=np.float32)

    # We want to project on the floor directly UNDER the object: Target is (90, 0, 0).
    proj_pixels_shadow = service.project_camera_to_projector(
        cam_pixels_offset, height_mm=100, target_z=0, prefer_homography=False
    )

    # Projector at (200, 0, 1000). Target at (90, 0, 0).
    # dx = 90 - 200 = -110. dz = -1000.
    # x_norm = -110/1000 = -0.11.
    # pixel_x = 500 + (-0.11 * 1000) = 390.
    assert proj_pixels_shadow[0, 0] == pytest.approx(390.0, abs=1e-2)


def test_projection_service_homography_parallax():
    # Same setup but using Homography
    camera_matrix = np.array(
        [[1000, 0, 500], [0, 1000, 500], [0, 0, 1]], dtype=np.float32
    )
    dist_coeffs = np.zeros(5, dtype=np.float32)
    rotation_matrix = np.array([[1, 0, 0], [0, -1, 0], [0, 0, -1]], dtype=np.float32)
    rvec, _ = cv2.Rodrigues(rotation_matrix)
    tvec = np.array([[0], [0], [1000]], dtype=np.float32)
    camera_model = CameraProjectionModel(camera_matrix, dist_coeffs, rvec, tvec)

    # Homography maps Camera Pixels (at Z=0) to Projector Pixels (at Z=0)
    # Projector at (200, 0, 1000)
    # Camera pixel (500, 500) sees World(0, 0, 0)
    # Projector pixel (300, 500) hits World(0, 0, 0)
    # So H maps (500, 500) -> (300, 500)
    # For a simple translation, H is [[1, 0, -200], [0, 1, 0], [0, 0, 1]]
    # But it's in pixel space. 100mm = 100 pixels (since f=1000 and Z=1000)
    # dx = -200mm => du = -200 pixels
    homography_matrix = np.array([[1, 0, -200], [0, 1, 0], [0, 0, 1]], dtype=np.float32)

    proj_center = np.array([200.0, 0.0, 1000.0])
    proj_tvec_fixed = -(rotation_matrix @ proj_center).reshape(3, 1)

    projector_model = Projector3DModel(
        homography_matrix=homography_matrix,
        rotation_vector=rvec,  # Need these for projector_center calculation
        translation_vector=proj_tvec_fixed,
        use_3d=False,
    )

    service = ProjectionService(camera_model, projector_model)

    # --- TEST: Object at height 100mm, we want to hit it ---
    cam_pixels = np.array(
        [[500, 500]], dtype=np.float32
    )  # Camera sees top of token at (0,0,100)
    # Correct projector pixel to hit (0,0,100) is 277.77 (from previous test)
    proj_pixels = service.project_camera_to_projector(
        cam_pixels, height_mm=100, target_z=100, prefer_homography=True
    )

    assert proj_pixels[0, 0] == pytest.approx(
        277.777, abs=1.0
    )  # Allow some tolerance for homography vs 3D
