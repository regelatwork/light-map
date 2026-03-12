from multiprocessing import Queue, Event
from fastapi.testclient import TestClient
from light_map.vision.remote_driver import create_app
from light_map.common_types import ResultType


def test_remote_driver_grid_config_endpoint():
    results_queue = Queue()
    stop_event = Event()
    state_mirror = {}

    app = create_app(results_queue, stop_event, state_mirror)
    client = TestClient(app)

    # 1. Update grid with only offset
    grid_data = {"offset_x": 120.5, "offset_y": 240.2}
    response = client.post("/config/grid", json=grid_data)
    assert response.status_code == 200

    result = results_queue.get(timeout=1.0)
    assert result.type == ResultType.ACTION
    assert result.data["action"] == "UPDATE_GRID"
    assert result.data["offset_x"] == 120.5
    assert result.data["offset_y"] == 240.2
    assert result.data["spacing"] is None

    # 2. Update grid with offset and spacing
    grid_data_full = {"offset_x": 150.0, "offset_y": 300.0, "spacing": 64.5}
    response = client.post("/config/grid", json=grid_data_full)
    assert response.status_code == 200

    result = results_queue.get(timeout=1.0)
    assert result.type == ResultType.ACTION
    assert result.data["action"] == "UPDATE_GRID"
    assert result.data["offset_x"] == 150.0
    assert result.data["offset_y"] == 300.0
    assert result.data["spacing"] == 64.5
