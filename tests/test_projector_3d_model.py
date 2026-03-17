import unittest
import numpy as np
import cv2
from light_map.vision.projection import Projector3DModel
from light_map.calibration_logic import calibrate_projector_3d


class TestProjector3DModel(unittest.TestCase):
    def test_fallback_to_homography(self):
        # Create a dummy homography (identity)
        H = np.eye(3, dtype=np.float32)
        model = Projector3DModel(homography=H, use_3d=False)

        # Test points (X, Y, Z)
        pts_3d = np.array([[10, 20, 0], [100, 200, 50]], dtype=np.float32)

        # In fallback mode, it should only use X, Y and the homography
        # Since H is identity, results should match X, Y
        proj_pts = model.project_world_to_projector(pts_3d)

        self.assertEqual(proj_pts.shape, (2, 2))
        np.testing.assert_array_almost_equal(proj_pts[0], [10, 20])
        np.testing.assert_array_almost_equal(proj_pts[1], [100, 200])

    def test_3d_projection(self):
        # Simple camera-like projection
        # Looking down from Z=1000, no rotation
        mtx = np.array([[1000, 0, 640], [0, 1000, 360], [0, 0, 1]], dtype=np.float32)
        dist = np.zeros(5, dtype=np.float32)
        rvec = np.array(
            [np.pi, 0, 0], dtype=np.float32
        )  # Rotated 180 around X to look down
        tvec = np.array([0, 0, 1000], dtype=np.float32)

        model = Projector3DModel(mtx=mtx, dist=dist, rvec=rvec, tvec=tvec, use_3d=True)

        # Point at origin in world space (0, 0, 0)
        pts_3d = np.array([[0, 0, 0]], dtype=np.float32)

        # C is at (0, 0, 1000). Table is at Z=0.
        # Ray goes from (0,0,1000) through (0,0,0).
        # Should project to the principal point (640, 360)
        proj_pts = model.project_world_to_projector(pts_3d)

        np.testing.assert_array_almost_equal(proj_pts[0], [640, 360], decimal=1)

    def test_solver_synthetic(self):
        # Generate synthetic data
        # Known projector parameters
        res = (1280, 720)
        true_mtx = np.array(
            [[1000, 0, 640], [0, 1000, 360], [0, 0, 1]], dtype=np.float32
        )
        true_dist = np.zeros(5, dtype=np.float32)
        true_rvec = np.array([np.pi, 0, 0], dtype=np.float32)
        true_tvec = np.array([100, 200, 1500], dtype=np.float32)

        # Create 3D points at different heights
        obj_points = []
        for x in range(-500, 501, 250):
            for y in range(-400, 401, 200):
                for z in [0, 100]:
                    obj_points.append([float(x), float(y), float(z)])
        obj_points = np.array(obj_points, dtype=np.float32)

        # Project to find 2D correspondences
        img_points, _ = cv2.projectPoints(
            obj_points, true_rvec, true_tvec, true_mtx, true_dist
        )
        img_points = img_points.reshape(-1, 2)

        # Package as correspondences
        correspondences = [
            (obj_points[i], img_points[i]) for i in range(len(obj_points))
        ]

        # Solve
        result = calibrate_projector_3d(correspondences, res)

        self.assertIsNotNone(result)
        mtx, dist, rvec, tvec, rms = result

        # Verify RMS is very low (it's perfect synthetic data)
        self.assertLess(rms, 0.1)

        # Verify intrinsic matrix is close
        np.testing.assert_array_almost_equal(mtx, true_mtx, decimal=0)

        # Verify pose is close
        # Rotation can sometimes have different representations, so check rotation matrix
        true_R, _ = cv2.Rodrigues(true_rvec)
        sol_R, _ = cv2.Rodrigues(rvec)
        np.testing.assert_array_almost_equal(sol_R, true_R, decimal=2)
        np.testing.assert_array_almost_equal(
            tvec.flatten(), true_tvec.flatten(), decimal=0
        )

    def test_solver_noisy(self):
        # Similar to synthetic but with noise
        res = (1280, 720)
        true_mtx = np.array(
            [[1000, 0, 640], [0, 1000, 360], [0, 0, 1]], dtype=np.float32
        )
        true_dist = np.zeros(5, dtype=np.float32)
        true_rvec = np.array([np.pi, 0, 0], dtype=np.float32)
        true_tvec = np.array([0, 0, 1200], dtype=np.float32)

        obj_points = []
        for x in range(-400, 401, 200):
            for y in range(-300, 301, 150):
                for z in [0, 80]:
                    obj_points.append([float(x), float(y), float(z)])
        obj_points = np.array(obj_points, dtype=np.float32)

        img_points, _ = cv2.projectPoints(
            obj_points, true_rvec, true_tvec, true_mtx, true_dist
        )
        img_points = img_points.reshape(-1, 2)

        # Add 0.5 pixel Gaussian noise
        np.random.seed(42)
        img_points += np.random.normal(0, 0.5, img_points.shape).astype(np.float32)

        correspondences = [
            (obj_points[i], img_points[i]) for i in range(len(obj_points))
        ]
        result = calibrate_projector_3d(correspondences, res)

        self.assertIsNotNone(result)
        mtx, dist, rvec, tvec, rms = result

        # Verify RMS reflects noise level (approx 0.5)
        self.assertLess(rms, 1.5)
        # Verify parameters are still reasonably close
        np.testing.assert_array_almost_equal(
            mtx, true_mtx, decimal=-1
        )  # Within 10px focal length

    def test_projection_consistency(self):
        """Verifies that 3D model at Z=0 matches a Homography built from the same data."""
        mtx = np.array([[1000, 0, 640], [0, 1000, 360], [0, 0, 1]], dtype=np.float32)
        rvec = np.array([np.pi, 0.1, 0.1], dtype=np.float32)  # Slight tilt
        tvec = np.array([50, -50, 1500], dtype=np.float32)

        # 1. Create a set of points at Z=0
        world_pts_3d = []
        for x in range(-500, 501, 250):
            for y in range(-400, 401, 200):
                world_pts_3d.append([float(x), float(y), 0.0])
        world_pts_3d = np.array(world_pts_3d, dtype=np.float32)

        # 2. Project them using 3D model
        proj_pts_3d, _ = cv2.projectPoints(world_pts_3d, rvec, tvec, mtx, None)
        proj_pts_3d = proj_pts_3d.reshape(-1, 2)

        # 3. Build a Homography from World(X,Y) to Projector(u,v)
        H, _ = cv2.findHomography(world_pts_3d[:, :2], proj_pts_3d)

        # 4. Create Projector3DModel with both
        model = Projector3DModel(
            mtx=mtx, rvec=rvec, tvec=tvec, homography=H, use_3d=True
        )

        # 5. Test point at Z=0
        test_pt = np.array([[123.0, 456.0, 0.0]], dtype=np.float32)

        # Result using 3D path
        res_3d = model.project_world_to_projector(test_pt)

        # Result using Homography path
        model.use_3d = False
        res_2d = model.project_world_to_projector(test_pt)

        # They should be very close for Z=0
        np.testing.assert_array_almost_equal(res_3d, res_2d, decimal=1)


if __name__ == "__main__":
    unittest.main()
