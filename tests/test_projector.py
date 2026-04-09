import numpy as np
from light_map.rendering.projector import generate_calibration_pattern


def test_generate_calibration_pattern_dimensions():
    width = 800
    height = 600
    rows = 4
    cols = 5

    img, params = generate_calibration_pattern(width, height, rows, cols)

    assert img.shape == (height, width, 3)
    assert img.dtype == np.uint8
    assert params["rows"] == rows
    assert params["cols"] == cols
    assert "start_x" in params
    assert "start_y" in params

    # Calculate expected square size
    # Max width available: 800 - 200 (default border 100 * 2) = 600
    # Max height available: 600 - 200 = 400
    # Max sq width = 600 // 5 = 120
    # Max sq height = 400 // 4 = 100
    # Expected sq size = 100
    expected_sq = 100
    assert params["square_size"] == expected_sq


def test_generate_calibration_pattern_colors():
    # Test a small pattern
    width = 400
    height = 400
    rows = 2
    cols = 2

    img, _ = generate_calibration_pattern(width, height, rows, cols, border_size=50)

    # Check for presence of Black (0) and White (255)
    assert np.any(img == 0)
    assert np.any(img == 255)
