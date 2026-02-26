import pytest
from light_map.vision.token_filter import TokenFilter
from light_map.common_types import Token


def test_token_filter_masking_within_bounds():
    filter = TokenFilter()
    # Token at (50, 50) in map area (0, 0, 100, 100)
    t1 = Token(id=1, world_x=50.0, world_y=50.0)
    filtered = filter.update([t1], 0.0, map_bounds=(0.0, 0.0, 100.0, 100.0))
    assert len(filtered) == 1
    assert filtered[0].id == 1


def test_token_filter_masking_outside_bounds_x():
    filter = TokenFilter()
    # Token at (150, 50) outside map area (0, 0, 100, 100)
    t1 = Token(id=1, world_x=150.0, world_y=50.0)
    filtered = filter.update([t1], 0.0, map_bounds=(0.0, 0.0, 100.0, 100.0))
    assert len(filtered) == 0


def test_token_filter_masking_outside_bounds_y():
    filter = TokenFilter()
    # Token at (50, 150) outside map area (0, 0, 100, 100)
    t1 = Token(id=1, world_x=50.0, world_y=150.0)
    filtered = filter.update([t1], 0.0, map_bounds=(0.0, 0.0, 100.0, 100.0))
    assert len(filtered) == 0


def test_token_filter_masking_negative_coordinates():
    filter = TokenFilter()
    # Token at (-10, 50) outside map area (0, 0, 100, 100)
    t1 = Token(id=1, world_x=-10.0, world_y=50.0)
    filtered = filter.update([t1], 0.0, map_bounds=(0.0, 0.0, 100.0, 100.0))
    assert len(filtered) == 0


def test_token_filter_masking_with_offset_bounds():
    filter = TokenFilter()
    # Token at (0, 0) should be INSIDE bounds (-100, -100, 100, 100)
    t1 = Token(id=1, world_x=0.0, world_y=0.0)
    filtered = filter.update([t1], 0.0, map_bounds=(-100.0, -100.0, 100.0, 100.0))
    assert len(filtered) == 1

    # Token at (-150, 0) should be OUTSIDE
    t1 = Token(id=1, world_x=-150.0, world_y=0.0)
    filtered = filter.update([t1], 0.0, map_bounds=(-100.0, -100.0, 100.0, 100.0))
    assert len(filtered) == 0


def test_token_filter_masking_disabled_when_bounds_none():
    filter = TokenFilter()
    # Token at (150, 50) should be kept if no bounds are specified
    t1 = Token(id=1, world_x=150.0, world_y=50.0)
    filtered = filter.update([t1], 0.0, map_bounds=None)
    assert len(filtered) == 1


if __name__ == "__main__":
    pytest.main([__file__])
