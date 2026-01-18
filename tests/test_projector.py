import numpy as np
import pytest
from src.light_map.projector import generate_calibration_pattern

def test_generate_calibration_pattern_dimensions():
    width = 800
    height = 600
    rows = 4
    cols = 5
    
    img, params = generate_calibration_pattern(width, height, rows, cols)
    
    assert img.shape == (height, width, 3)
    assert img.dtype == np.uint8
    assert params['rows'] == rows
    assert params['cols'] == cols

def test_generate_calibration_pattern_colors():
    # Test a small 2x2 pattern
    width = 200
    height = 200
    rows = 2
    cols = 2
    border = 0
    
    # We need to expose or control border size for precise pixel testing
    # The current implementation has hardcoded square_size=100 in the function body?
    # Let's check the code I wrote. 
    # Yes, "square_size = 100".
    # So a 2x2 pattern needs at least 200x200 + border.
    
    # Let's just check that we have black and white pixels
    img, _ = generate_calibration_pattern(400, 400, 2, 2)
    
    # Check for presence of Black (0) and White (255)
    assert np.any(img == 0)
    assert np.any(img == 255)
