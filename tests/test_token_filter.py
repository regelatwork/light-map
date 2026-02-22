import pytest
import time
from light_map.vision.token_filter import TokenFilter
from light_map.common_types import Token


def test_token_filter_temporal_smoothing():
    filter = TokenFilter(alpha=0.5)

    # Detection 1
    t1 = Token(id=1, world_x=100.0, world_y=100.0)
    filtered = filter.update([t1], time.monotonic())

    assert len(filtered) == 1
    assert filtered[0].world_x == 100.0

    # Detection 2 (moved to 200, 200)
    t2 = Token(id=1, world_x=200.0, world_y=200.0)
    filtered = filter.update([t2], time.monotonic())

    # With alpha=0.5: 100 * 0.5 + 200 * 0.5 = 150
    assert filtered[0].world_x == pytest.approx(150.0)
    assert filtered[0].world_y == pytest.approx(150.0)


def test_token_filter_occlusion_buffer():
    # 100ms timeout
    filter = TokenFilter(occlusion_timeout_ms=100.0)

    # Seen at T=0
    t1 = Token(id=1, world_x=100.0, world_y=100.0)
    filter.update([t1], 0.0)

    # Lost at T=50ms
    filtered = filter.update([], 0.05)
    assert len(filtered) == 1
    assert filtered[0].id == 1
    assert filtered[0].is_occluded

    # Still lost at T=150ms (timeout expired)
    filtered = filter.update([], 0.15)
    assert len(filtered) == 0


def test_token_filter_grid_snapping_odd():
    filter = TokenFilter()

    # Grid spacing 100, origin (0,0)
    # Token at (120, 130)
    # Cell is (1, 1), center is (150, 150)
    t1 = Token(id=1, world_x=120.0, world_y=130.0)

    # Size 1 (Odd)
    filtered = filter.update(
        [t1], 0.0, grid_spacing=100.0, token_configs={1: {"size": 1}}
    )
    assert filtered[0].world_x == 150.0
    assert filtered[0].world_y == 150.0
    assert filtered[0].grid_x == 1
    assert filtered[0].grid_y == 1


def test_token_filter_grid_snapping_even():
    filter = TokenFilter()

    # Token at (120, 130)
    # Nearest intersection for even size (2) is (100, 100)?
    # Wait, even sizes snap to CORNERS (integers)
    t1 = Token(id=1, world_x=120.0, world_y=130.0)

    # Size 2 (Even)
    filtered = filter.update(
        [t1], 0.0, grid_spacing=100.0, token_configs={1: {"size": 2}}
    )
    assert filtered[0].world_x == 100.0
    assert filtered[0].world_y == 100.0
    assert filtered[0].grid_x == 1
    assert filtered[0].grid_y == 1


if __name__ == "__main__":
    pytest.main([__file__])
