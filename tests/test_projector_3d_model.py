import unittest
import cv2
import numpy as np
from light_map.rendering.projection import Projector3DModel

class TestProjector3DModel(unittest.TestCase):
    def test_fallback_to_world_coords(self):
        # Create a dummy homography (identity) - should be IGNORED by project_world_to_projector
        homography_matrix = np.eye(3, dtype=np.float32)
        model = Projector3DModel(homography_matrix=homography_matrix, use_3d=False)
        
        # Test points (X, Y, Z)
        world_points_3d = np.array([[10, 20, 0], [100, 200, 50]], dtype=np.float32)
        
        # In fallback mode, project_world_to_projector should return X, Y directly
        # (It leaves actual homography application to ProjectionService which handles camera pixels)
        projector_pixels = model.project_world_to_projector(world_points_3d)
        
        self.assertEqual(projector_pixels.shape, (2, 2))
        np.testing.assert_array_almost_equal(projector_pixels[0], [10, 20])
        np.testing.assert_array_almost_equal(projector_pixels[1], [100, 200])
        
    def test_3d_projection(self):
        # Simple camera-like projection
        # Looking down from Z=1000, no rotation
        intrinsic_matrix = np.array([[1000, 0, 640], [0, 1000, 360], [0, 0, 1]], dtype=np.float32)
        distortion_coefficients = np.zeros(5, dtype=np.float32)
        rotation_vector = np.array([np.pi, 0, 0], dtype=np.float32)  # Rotated 180 around X to look down
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
        
    def test_projection_consistency(self):
        """Verifies that 3D model returns world X,Y when use_3d=False."""
        intrinsic_matrix = np.array([[1000, 0, 640], [0, 1000, 360], [0, 0, 1]], dtype=np.float32)
        rotation_vector = np.array([np.pi, 0.1, 0.1], dtype=np.float32)  # Slight tilt
        translation_vector = np.array([50, -50, 1500], dtype=np.float32)
        
        model = Projector3DModel(
            intrinsic_matrix=intrinsic_matrix,
            rotation_vector=rotation_vector,
            translation_vector=translation_vector,
            use_3d=True,
        )
        
        # 5. Test point at Z=0
        test_point = np.array([[123.0, 456.0, 0.0]], dtype=np.float32)
        
        # Result using 3D path
        result_3d = model.project_world_to_projector(test_point)
        
        # Result using Fallback path (should be X, Y of test point)
        model.use_3d = False
        result_fallback = model.project_world_to_projector(test_point)
        
        np.testing.assert_array_almost_equal(result_fallback, [[123.0, 456.0]], decimal=1)
        # Note: result_3d will NOT match result_fallback unless calibration is perfect identity/scale
        self.assertFalse(np.array_equal(result_3d, result_fallback))
        
if __name__ == "__main__":
    unittest.main()
