from light_map.core.common_types import Token

def test_token_to_dict_includes_bonuses():
    token = Token(id=1, world_x=10.0, world_y=20.0, cover_bonus=2, reflex_bonus=1)
    d = token.to_dict()
    assert d["cover_bonus"] == 2
    assert d["reflex_bonus"] == 1
