import unittest
import numpy as np
import cv2
from light_map.vision.projection import Projector3DModel
from light_map.calibration_logic import calibrate_projector_3d


class TestProjector3DModel(unittest.TestCase):
    def test_fallback_to_homography(self):
        # Create a dummy homography (identity)
        homography_matrix = np.eye(3, dtype=np.float32)
        model = Projector3DModel(homography_matrix=homography_matrix, use_3d=False)

        # Test points (X, Y, Z)
        world_points_3d = np.array([[10, 20, 0], [100, 200, 50]], dtype=np.float32)

        # In fallback mode, it should only use X, Y and the homography
        # Since H is identity, results should match X, Y
        projector_pixels = model.project_world_to_projector(world_points_3d)

        self.assertEqual(projector_pixels.shape, (2, 2))
        np.testing.assert_array_almost_equal(projector_pixels[0], [10, 20])
        np.testing.assert_array_almost_equal(projector_pixels[1], [100, 200])

    def test_3d_projection(self):
        # Simple camera-like projection
        # Looking down from Z=1000, no rotation
        intrinsic_matrix = np.array(
            [[1000, 0, 640], [0, 1000, 360], [0, 0, 1]], dtype=np.float32
        )
        distortion_coefficients = np.zeros(5, dtype=np.float32)
        rotation_vector = np.array(
            [np.pi, 0, 0], dtype=np.float32
        )  # Rotated 180 around X to look down
        translation_vector = np.array([0, 0, 1000], dtype=np.float32)

        model = Projector3DModel(
            intrinsic_matrix=intrinsic_matrix,
            distortion_coefficients=distortion_coefficients,
            rotation_vector=rotation_vector,
            translation_vector=translation_vector,
            use_3d=True,
        )

        # Point at origin in world space (0, 0, 0)
        world_points_3d = np.array([[0, 0, 0]], dtype=np.float32)

        # C is at (0, 0, 1000). Table is at Z=0.
        # Ray goes from (0,0,1000) through (0,0,0).
        # Should project to the principal point (640, 360)
        projector_pixels = model.project_world_to_projector(world_points_3d)

        np.testing.assert_array_almost_equal(projector_pixels[0], [640, 360], decimal=1)

    def test_solver_synthetic(self):
        # Generate synthetic data
        # Known projector parameters
        resolution = (1280, 720)
        true_intrinsic_matrix = np.array(
            [[1000, 0, 640], [0, 1000, 360], [0, 0, 1]], dtype=np.float32
        )
        true_distortion_coefficients = np.zeros(5, dtype=np.float32)
        true_rotation_vector = np.array([np.pi, 0, 0], dtype=np.float32)
        true_translation_vector = np.array([100, 200, 1500], dtype=np.float32)

        # Create 3D points at different heights
        object_points = []
        for x in range(-500, 501, 250):
            for y in range(-400, 401, 200):
                for z in [0, 100]:
                    object_points.append([float(x), float(y), float(z)])
        object_points = np.array(object_points, dtype=np.float32)

        # Project to find 2D correspondences
        image_points, _ = cv2.projectPoints(
            object_points,
            true_rotation_vector,
            true_translation_vector,
            true_intrinsic_matrix,
            true_distortion_coefficients,
        )
        image_points = image_points.reshape(-1, 2)

        # Package as correspondences
        correspondences = [
            (object_points[i], image_points[i]) for i in range(len(object_points))
        ]

        # Solve
        result = calibrate_projector_3d(correspondences, resolution)

        self.assertIsNotNone(result)
        (
            intrinsic_matrix,
            distortion_coefficients,
            rotation_vector,
            translation_vector,
            rms,
        ) = result

        # Verify RMS is very low (it's perfect synthetic data)
        self.assertLess(rms, 0.1)

        # Verify intrinsic matrix is close
        np.testing.assert_array_almost_equal(
            intrinsic_matrix, true_intrinsic_matrix, decimal=0
        )

        # Verify pose is close
        # Rotation can sometimes have different representations, so check rotation matrix
        true_rotation_matrix, _ = cv2.Rodrigues(true_rotation_vector)
        sol_rotation_matrix, _ = cv2.Rodrigues(rotation_vector)
        np.testing.assert_array_almost_equal(
            sol_rotation_matrix, true_rotation_matrix, decimal=2
        )
        np.testing.assert_array_almost_equal(
            translation_vector.flatten(), true_translation_vector.flatten(), decimal=0
        )

    def test_solver_noisy(self):
        # Similar to synthetic but with noise
        resolution = (1280, 720)
        true_intrinsic_matrix = np.array(
            [[1000, 0, 640], [0, 1000, 360], [0, 0, 1]], dtype=np.float32
        )
        true_distortion_coefficients = np.zeros(5, dtype=np.float32)
        true_rotation_vector = np.array([np.pi, 0, 0], dtype=np.float32)
        true_translation_vector = np.array([0, 0, 1200], dtype=np.float32)

        object_points = []
        for x in range(-400, 401, 200):
            for y in range(-300, 301, 150):
                for z in [0, 80]:
                    object_points.append([float(x), float(y), float(z)])
        object_points = np.array(object_points, dtype=np.float32)

        image_points, _ = cv2.projectPoints(
            object_points,
            true_rotation_vector,
            true_translation_vector,
            true_intrinsic_matrix,
            true_distortion_coefficients,
        )
        image_points = image_points.reshape(-1, 2)

        # Add 0.5 pixel Gaussian noise
        np.random.seed(42)
        image_points += np.random.normal(0, 0.5, image_points.shape).astype(np.float32)

        correspondences = [
            (object_points[i], image_points[i]) for i in range(len(object_points))
        ]
        result = calibrate_projector_3d(correspondences, resolution)

        self.assertIsNotNone(result)
        (
            intrinsic_matrix,
            distortion_coefficients,
            rotation_vector,
            translation_vector,
            rms,
        ) = result

        # Verify RMS reflects noise level (approx 0.5)
        self.assertLess(rms, 1.5)
        # Verify parameters are still reasonably close
        np.testing.assert_array_almost_equal(
            intrinsic_matrix, true_intrinsic_matrix, decimal=-1
        )  # Within 10px focal length

    def test_projection_consistency(self):
        """Verifies that 3D model at Z=0 matches a Homography built from the same data."""
        intrinsic_matrix = np.array(
            [[1000, 0, 640], [0, 1000, 360], [0, 0, 1]], dtype=np.float32
        )
        rotation_vector = np.array([np.pi, 0.1, 0.1], dtype=np.float32)  # Slight tilt
        translation_vector = np.array([50, -50, 1500], dtype=np.float32)

        # 1. Create a set of points at Z=0
        world_points_3d = []
        for x in range(-500, 501, 250):
            for y in range(-400, 401, 200):
                world_points_3d.append([float(x), float(y), 0.0])
        world_points_3d = np.array(world_points_3d, dtype=np.float32)

        # 2. Project them using 3D model
        projector_pixels_3d, _ = cv2.projectPoints(
            world_points_3d, rotation_vector, translation_vector, intrinsic_matrix, None
        )
        projector_pixels_3d = projector_pixels_3d.reshape(-1, 2)

        # 3. Build a Homography from World(X,Y) to Projector(u,v)
        homography_matrix, _ = cv2.findHomography(
            world_points_3d[:, :2], projector_pixels_3d
        )

        # 4. Create Projector3DModel with both
        model = Projector3DModel(
            intrinsic_matrix=intrinsic_matrix,
            rotation_vector=rotation_vector,
            translation_vector=translation_vector,
            homography_matrix=homography_matrix,
            use_3d=True,
        )

        # 5. Test point at Z=0
        test_point = np.array([[123.0, 456.0, 0.0]], dtype=np.float32)

        # Result using 3D path
        result_3d = model.project_world_to_projector(test_point)

        # Result using Homography path
        model.use_3d = False
        result_2d = model.project_world_to_projector(test_point)

        # They should be very close for Z=0
        np.testing.assert_array_almost_equal(result_3d, result_2d, decimal=1)


if __name__ == "__main__":
    unittest.main()
