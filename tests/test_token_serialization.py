from light_map.core.common_types import Token


def test_token_serialization_basic():
    """Verifies that Token can be serialized to dict correctly."""
    token = Token(id=1, world_x=10.0, world_y=20.0)
    data = token.to_dict()

    assert data["id"] == 1
    assert data["world_x"] == 10.0
    assert data["world_y"] == 20.0
    assert "cover_bonus" not in data  # Should not be in dict anymore
