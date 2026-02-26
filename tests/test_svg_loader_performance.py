import unittest
import numpy as np
import os
from unittest.mock import patch
import sys

# Ensure we can import the local package
sys.path.insert(0, os.path.abspath("src"))

from light_map.svg_loader import SVGLoader


class TestSVGLoaderPerformance(unittest.TestCase):
    def setUp(self):
        # Create a dummy SVG file for testing
        self.svg_path = "tests/test_perf.svg"
        with open(self.svg_path, "w") as f:
            f.write(
                '<svg width="100" height="100"><rect x="10" y="10" width="80" height="80" fill="red" /></svg>'
            )

        self.loader = SVGLoader(self.svg_path)

    def tearDown(self):
        if os.path.exists(self.svg_path):
            os.remove(self.svg_path)

    def test_render_output_shape(self):
        """Verify that render returns an image of the requested size regardless of quality."""
        w, h = 200, 100
        img = self.loader.render(w, h, quality=0.5)
        self.assertEqual(img.shape, (h, w, 3))

        img_full = self.loader.render(w, h, quality=1.0)
        self.assertEqual(img_full.shape, (h, w, 3))

    def test_caching_mechanism(self):
        """Verify that repeated calls with same parameters return the same object."""
        # First call
        img1 = self.loader.render(100, 100, quality=1.0)

        # Second call with same params
        img2 = self.loader.render(100, 100, quality=1.0)

        # Should be the same object ID due to lru_cache
        self.assertIs(img1, img2, "Cached object should be identical")

        # Call with different params
        img3 = self.loader.render(100, 100, quality=0.5)
        self.assertIsNot(img1, img3, "Different params should return new object")

    def test_parameter_quantization(self):
        """Verify that slight float variations hit the same cache entry."""
        # render(..., scale_factor=1.00001) should map to 1.0
        img1 = self.loader.render(100, 100, scale_factor=1.00001)
        img2 = self.loader.render(100, 100, scale_factor=1.00002)

        self.assertIs(
            img1, img2, "Quantization should map slight variations to same cache entry"
        )

        # Large variation should differ
        img3 = self.loader.render(100, 100, scale_factor=1.1)
        self.assertIsNot(img1, img3)

    def test_internal_buffer_scaling(self):
        """
        Verify that the internal render uses a smaller buffer when quality < 1.0.
        We can inspect the _render_internal call by mocking it, or check artifacts (harder).
        Better to mock _render_internal and check arguments?
        But _render_internal is the one doing the work.
        We can check if the result is upscaled (blurry) vs sharp, but that's subjective.

        Let's patch cv2.resize to see if it gets called, which implies upscaling occurred.
        """
        with patch("cv2.resize") as mock_resize:
            # Configure mock to return a dummy image of correct size so render doesn't crash
            mock_resize.return_value = np.zeros((100, 200, 3), dtype=np.uint8)

            self.loader.render(200, 100, quality=0.5)

            # Should call resize once
            self.assertTrue(mock_resize.called)

            # Check args: source image should be 100x50 (0.5 scale)
            args, _ = mock_resize.call_args
            src_img = args[0]
            self.assertEqual(src_img.shape, (50, 100, 3))

    def test_quality_clamping(self):
        """Verify quality is clamped between 0.1 and 1.0"""
        # We can inspect the quantized quality passed to _render_internal

        # We need to bypass the lru_cache wrapper to inspect calls, or just trust the logic.
        # Let's trust logic but verify behavior:

        # Quality 0.0 -> Should behave like 0.1
        with patch("cv2.resize") as mock_resize:
            mock_resize.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
            self.loader.render(100, 100, quality=0.0)
            args, _ = mock_resize.call_args
            # 0.1 * 100 = 10
            self.assertEqual(args[0].shape, (10, 10, 3))

        # Quality 2.0 -> Should behave like 1.0 (no resize)
        with patch("cv2.resize") as mock_resize:
            self.loader.render(100, 100, quality=2.0)
            self.assertFalse(mock_resize.called)

    def test_pan_quantization(self):
        """Verify that slight float variations in pan hit the same cache entry."""
        img1 = self.loader.render(100, 100, offset_x=10.1, offset_y=20.2)
        img2 = self.loader.render(100, 100, offset_x=10.3, offset_y=20.4)
        self.assertIs(img1, img2, "Pan quantization should hit cache")


if __name__ == "__main__":
    unittest.main()
