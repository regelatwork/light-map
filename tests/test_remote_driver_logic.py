import pytest
from multiprocessing import Queue, Event
from fastapi.testclient import TestClient
from light_map.vision.remote_driver import create_app, RemoteHandInput, RemoteToken
from light_map.common_types import ResultType, DetectionResult

def test_remote_driver_hands_endpoint():
    results_queue = Queue()
    stop_event = Event()
    state_mirror = {}
    
    app = create_app(results_queue, stop_event, state_mirror)
    client = TestClient(app)
    
    hand_data = [
        {"x": 100, "y": 200, "gesture": "Pointing"},
        {"x": 300, "y": 400, "gesture": "Open Palm"}
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
    
    token_data = [
        {"id": 42, "x": 10.5, "y": 20.7, "angle": 45.0}
    ]
    
    response = client.post("/input/tokens", json=token_data)
    assert response.status_code == 200
    
    # Verify result in queue
    result = results_queue.get(timeout=1.0)
    assert isinstance(result, DetectionResult)
    assert result.type == ResultType.ARUCO
    assert len(result.data["tokens"]) == 1
    assert result.data["tokens"][0].id == 42
    assert result.data["tokens"][0].world_x == 10.5
