import numpy as np
from multiprocessing import Queue, Event
from fastapi.testclient import TestClient
from light_map.vision.remote_driver import create_app, numpy_to_python
from light_map.common_types import ResultType, DetectionResult


def test_numpy_to_python_converter():
    """Verifies that numpy_to_python correctly converts various numpy types."""
    data = {
        "array": np.array([1, 2, 3]),
        "float": np.float32(10.5),
        "int": np.int64(42),
        "bool": np.bool_(True),
        "nested": {"val": np.float64(1.23)},
        "list": [np.int32(1), np.int32(2)],
        "tuple": (np.float32(1.0),),
    }
    converted = numpy_to_python(data)
    assert isinstance(converted["array"], list)
    assert isinstance(converted["float"], float)
    assert isinstance(converted["int"], int)
    assert isinstance(converted["bool"], bool)
    assert isinstance(converted["nested"]["val"], float)
    assert isinstance(converted["list"][0], int)
    assert isinstance(converted["tuple"], list)
    assert isinstance(converted["tuple"][0], float)


def test_remote_driver_numpy_serialization():
    """Verifies that the API can handle numpy types in the state mirror."""
    results_queue = Queue()
    stop_event = Event()
    state_mirror = {
        "world": {
            "grid_spacing": np.float32(50.0),
            "offset": np.array([10.0, 20.0]),
            "active": np.bool_(True),
        }
    }

    app = create_app(results_queue, stop_event, state_mirror)
    client = TestClient(app)

    response = client.get("/state/world")
    assert response.status_code == 200
    data = response.json()
    assert data["grid_spacing"] == 50.0
    assert data["offset"] == [10.0, 20.0]
    assert data["active"] is True


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


def test_remote_driver_update_token_endpoint():
    results_queue = Queue()
    stop_event = Event()
    state_mirror = {}

    app = create_app(results_queue, stop_event, state_mirror)
    client = TestClient(app)

    # 1. Update basic fields
    response = client.put(
        "/state/tokens/123", json={"name": "New Name", "color": "#ff0000"}
    )
    assert response.status_code == 200

    result = results_queue.get(timeout=1.0)
    assert result.type == ResultType.ACTION
    assert result.data["action"] == "UPDATE_TOKEN"
    assert result.data["id"] == 123
    assert result.data["name"] == "New Name"
    assert result.data["color"] == "#ff0000"

    # 2. Update extended fields
    response = client.put(
        "/state/tokens/123",
        json={
            "type": "PC",
            "profile": "large_token",
            "size": 2,
            "height_mm": 25.5,
        },
    )
    assert response.status_code == 200

    result = results_queue.get(timeout=1.0)
    assert result.data["type"] == "PC"
    assert result.data["profile"] == "large_token"
    assert result.data["size"] == 2
    assert result.data["height_mm"] == 25.5
