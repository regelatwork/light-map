"""
Test suite for TokenManager.
"""

import json

import pytest

from light_map.calibration.token_manager import TokenManager


@pytest.fixture
def tmp_tokens(tmp_path):
    tokens_data = {
        "token_profiles": {
            "pc": {"size": 1, "height_mm": 50.0},
            "small": {"size": 1, "height_mm": 15.0},
        },
        "aruco_defaults": {
            "0": {
                "name": "Token 0",
                "type": "PC",
                "profile": "pc",
                "size": None,
                "height_mm": None,
            },
            "1": {
                "name": "Token 1",
                "type": "PC",
                "profile": "pc",
                "size": None,
                "height_mm": None,
            },
            "42": {
                "name": "Legacy",
                "type": "NPC",
                "profile": "small",
                "size": None,
                "height_mm": None,
            },
            "43": {
                "name": "No Height",
                "type": "NPC",
                "profile": "none",
                "size": None,
                "height_mm": -5.0,
            },
        },
    }
    # Correcting the nulls for json.dump
    tokens_data["aruco_defaults"]["0"]["size"] = None
    tokens_data["aruco_defaults"]["0"]["height_mm"] = None
    tokens_data["aruco_defaults"]["1"]["size"] = None
    tokens_data["aruco_defaults"]["1"]["height_mm"] = None
    tokens_data["aruco_defaults"]["42"]["size"] = None
    tokens_data["aruco_defaults"]["42"]["height_mm"] = None
    tokens_data["aruco_defaults"]["43"]["size"] = None
    tokens_data["aruco_defaults"]["43"]["height_mm"] = -5.0

    p = tmp_path / "tokens.json"
    with open(p, "w") as f:
        json.dump(tokens_data, f)
    return str(p)


def test_token_manager_loading(tmp_tokens):
    tm = TokenManager(tmp_tokens)
    assert tm.get_token_by_id("0").height_mm == 50.0
    assert tm.get_token_by_id("42").height_mm == 15.0


def test_get_candidate_tokens(tmp_tokens):
    tm = TokenManager(tmp_tokens)
    # IDs 0-10. Only 0 and 1 should be candidates (positive height).
    candidates = tm.get_candidate_tokens(range(0, 10))
    assert len(candidates) == 2
    assert [c.id for c in candidates] == ["0", "1"]


def test_get_candidate_tokens_no_positive_height(tmp_tokens):
    tm = TokenManager(tmp_tokens)
    # ID 43 has negative height
    candidates = tm.get_candidate_tokens(range(42, 44))
    # ID 42 has 15.0, ID 43 has -5.0
    assert len(candidates) == 1
    assert candidates[0].id == "42"
