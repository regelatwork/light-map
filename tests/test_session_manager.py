import pytest
import os
import shutil
from light_map.map.session_manager import SessionManager, SESSION_DIR
from light_map.core.common_types import SessionData, ViewportState


@pytest.fixture
def clean_session_dir():
    if os.path.exists(SESSION_DIR):
        shutil.rmtree(SESSION_DIR)
    yield
    if os.path.exists(SESSION_DIR):
        shutil.rmtree(SESSION_DIR)


def test_get_session_path():
    path1 = SessionManager.get_session_path("/maps/dungeon.svg")
    path2 = SessionManager.get_session_path("/maps/dungeon.svg")
    path3 = SessionManager.get_session_path("/maps/cave.svg")

    assert path1 == path2
    assert path1 != path3
    assert path1.startswith(SESSION_DIR)
    assert path1.endswith(".json")


def test_save_and_load_for_map(clean_session_dir):
    map_path = "/maps/test_map.svg"
    data = SessionData(
        map_file=map_path, viewport=ViewportState(x=10, y=20, zoom=2.0), tokens=[]
    )

    # Save
    saved = SessionManager.save_for_map(map_path, data)
    assert saved is True
    assert os.path.exists(SessionManager.get_session_path(map_path))

    # Load
    loaded = SessionManager.load_for_map(map_path)
    assert loaded is not None
    assert loaded.map_file == map_path
    assert loaded.viewport.x == 10
    assert loaded.viewport.zoom == 2.0


def test_has_session(clean_session_dir):
    map_path = "/maps/exists.svg"
    no_map_path = "/maps/missing.svg"

    assert SessionManager.has_session(map_path) is False

    data = SessionData(map_file=map_path, viewport=ViewportState(), tokens=[])
    SessionManager.save_for_map(map_path, data)

    assert SessionManager.has_session(map_path) is True
    assert SessionManager.has_session(no_map_path) is False


def test_save_load_with_tokens_and_doors(tmp_path):
    from light_map.core.common_types import Token

    map_path = str(tmp_path / "map.svg")
    session_dir = str(tmp_path / "sessions")

    tokens = [
        Token(id=1, world_x=100.0, world_y=200.0, confidence=0.9),
        Token(id=2, world_x=300.0, world_y=400.0, name="Orc"),
    ]
    data = SessionData(
        map_file=map_path,
        viewport=ViewportState(zoom=1.5),
        tokens=tokens,
        door_states={"door1": True, "door2": False},
    )

    # Save
    SessionManager.save_for_map(map_path, data, session_dir=session_dir)

    # Load
    loaded = SessionManager.load_for_map(map_path, session_dir=session_dir)
    assert loaded is not None
    assert len(loaded.tokens) == 2
    assert loaded.tokens[0].id == 1
    assert loaded.tokens[0].world_x == 100.0
    assert loaded.tokens[0].confidence == 0.9
    assert loaded.tokens[1].id == 2
    assert loaded.tokens[1].name == "Orc"
    assert loaded.door_states["door1"] is True
    assert loaded.door_states["door2"] is False
