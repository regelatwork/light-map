from multiprocessing import Queue, Event
from fastapi.testclient import TestClient
from light_map.vision.remote_driver import create_app
from light_map.common_types import ResultType, DetectionResult


def test_remote_driver_hands_endpoint():
    results_queue = Queue()
    stop_event = Event()
    state_mirror = {}

    app = create_app(results_queue, stop_event, state_mirror)
    client = TestClient(app)

    hand_data = [
        {"x": 100, "y": 200, "gesture": "Pointing"},
        {"x": 300, "y": 400, "gesture": "Open Palm"},
    ]

    response = client.post("/input/hands", json=hand_data)
    assert response.status_code == 200

    # Verify result in queue
    result = results_queue.get(timeout=1.0)
    assert isinstance(result, DetectionResult)
    assert result.type == ResultType.HANDS
    assert len(result.data) == 2
    assert result.data[0].proj_pos == (100, 200)
    assert result.data[0].gesture == "Pointing"


def test_remote_driver_tokens_endpoint():
    results_queue = Queue()
    stop_event = Event()
    state_mirror = {}

    app = create_app(results_queue, stop_event, state_mirror)
    client = TestClient(app)

    token_data = [{"id": 42, "x": 10.5, "y": 20.7, "angle": 45.0}]

    response = client.post("/input/tokens", json=token_data)
    assert response.status_code == 200

    # Verify result in queue
    result = results_queue.get(timeout=1.0)
    assert isinstance(result, DetectionResult)
    assert result.type == ResultType.ARUCO
    assert len(result.data["tokens"]) == 1
    assert result.data["tokens"][0].id == 42
    assert result.data["tokens"][0].world_x == 10.5


def test_remote_driver_state_inspection():
    results_queue = Queue()
    stop_event = Event()
    state_mirror = {
        "world": {"scene": "MAP", "fps": 60.0},
        "tokens": [{"id": 1, "world_x": 100, "world_y": 200}],
        "menu": {"title": "Main Menu"},
    }

    app = create_app(results_queue, stop_event, state_mirror)
    client = TestClient(app)

    response = client.get("/state/world")
    assert response.status_code == 200
    assert response.json()["scene"] == "MAP"

    response = client.get("/state/tokens")
    assert response.status_code == 200
    assert response.json()[0]["id"] == 1

    response = client.get("/state/menu")
    assert response.status_code == 200
    assert response.json()["title"] == "Main Menu"


def test_remote_driver_action_endpoint():
    results_queue = Queue()
    stop_event = Event()
    state_mirror = {}

    app = create_app(results_queue, stop_event, state_mirror)
    client = TestClient(app)

    # 1. Action without payload
    response = client.post("/input/action", params={"action": "SYNC_VISION"})
    assert response.status_code == 200

    result = results_queue.get(timeout=1.0)
    assert result.type == ResultType.ACTION
    assert result.data["action"] == "SYNC_VISION"
    assert result.data["payload"] is None

    # 2. Action with payload
    response = client.post(
        "/input/action", params={"action": "LOAD_MAP", "payload": "maps/test.svg"}
    )
    assert response.status_code == 200

    result = results_queue.get(timeout=1.0)
    assert result.type == ResultType.ACTION
    assert result.data["action"] == "LOAD_MAP"
    assert result.data["payload"] == "maps/test.svg"


def test_remote_driver_reset_zoom_action():
    results_queue = Queue()
    stop_event = Event()
    state_mirror = {}

    app = create_app(results_queue, stop_event, state_mirror)
    client = TestClient(app)

    response = client.post("/input/action", params={"action": "RESET_ZOOM"})
    assert response.status_code == 200

    result = results_queue.get(timeout=1.0)
    assert result.type == ResultType.ACTION
    assert result.data["action"] == "RESET_ZOOM"
    assert result.data["payload"] is None


def test_remote_driver_zoom_endpoint():
    results_queue = Queue()
    stop_event = Event()
    state_mirror = {}

    app = create_app(results_queue, stop_event, state_mirror)
    client = TestClient(app)

    response = client.post("/map/zoom", params={"delta": 0.5})
    assert response.status_code == 200

    result = results_queue.get(timeout=1.0)
    assert result.type == ResultType.ACTION
    assert result.data["action"] == "ZOOM"
    assert result.data["delta"] == 0.5
