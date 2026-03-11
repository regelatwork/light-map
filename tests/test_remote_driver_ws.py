from multiprocessing import Queue, Event
from fastapi.testclient import TestClient
from light_map.vision.remote_driver import create_app
import time


def test_remote_driver_websocket_broadcast():
    results_queue = Queue()
    stop_event = Event()
    state_mirror = {
        "world": {"scene": "MAP", "fps": 60.0},
        "tokens": [{"id": 1, "world_x": 100, "world_y": 200}],
        "menu": {"title": "Main Menu"},
    }

    app = create_app(results_queue, stop_event, state_mirror)

    # Use TestClient as a context manager to trigger startup events
    with TestClient(app) as client:
        with client.websocket_connect("/ws/state") as websocket:
            # The background task should broadcast the state at ~30Hz
            # We wait for the first message
            data = websocket.receive_json()

            assert "world" in data
            assert data["world"]["scene"] == "MAP"
            assert "tokens" in data
            assert data["tokens"][0]["id"] == 1
            assert "menu" in data
            assert data["menu"]["title"] == "Main Menu"
            assert "timestamp" in data

            # Update the state mirror and check for another broadcast
            state_mirror["world"]["scene"] = "CALIBRATION"

            # Wait for the next broadcast (max 100ms)
            start_time = time.time()
            received_update = False
            while time.time() - start_time < 0.5:
                data = websocket.receive_json()
                if data["world"]["scene"] == "CALIBRATION":
                    received_update = True
                    break

            assert received_update, "Did not receive updated state via WebSocket"


def test_remote_driver_websocket_disconnect_handling():
    results_queue = Queue()
    stop_event = Event()
    state_mirror = {}

    app = create_app(results_queue, stop_event, state_mirror)

    with TestClient(app) as client:
        # Connect and immediately disconnect
        with client.websocket_connect("/ws/state") as _:
            pass

        # The manager should handle the disconnect without crashing
        # We can't easily inspect the internal manager state from here,
        # but we can verify the app is still healthy.
        response = client.get("/health")
        assert response.status_code == 200
