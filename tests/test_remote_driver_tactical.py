import pytest
from fastapi.testclient import TestClient
from light_map.vision.remote.remote_driver import create_app
from multiprocessing import Queue, Event

@pytest.fixture
def client():
    results_queue = Queue()
    stop_event = Event()
    state_mirror = {
        "tactical_bonuses": {
            "2": {
                "ac_bonus": 4,
                "reflex_bonus": 2,
                "best_apex": [50, 50],
                "segments": [{"start_idx": 0, "end_idx": 10, "status": 2}],
                "npc_pixels": [[100, 100], [101, 101]],
                "explanation": "Standard Cover (+4 AC)"
            }
        }
    }
    app = create_app(results_queue, stop_event, state_mirror)
    return TestClient(app)

def test_get_tactical_cover(client):
    response = client.get("/tactical/cover?attacker_id=1")
    assert response.status_code == 200
    data = response.json()
    assert "2" in data
    assert data["2"]["ac_bonus"] == 4
    assert data["2"]["explanation"] == "Standard Cover (+4 AC)"
    assert data["2"]["best_apex"] == [50, 50]

def test_get_tactical_cover_no_id(client):
    response = client.get("/tactical/cover")
    assert response.status_code == 200
    data = response.json()
    assert "2" in data
