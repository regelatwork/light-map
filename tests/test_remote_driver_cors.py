from multiprocessing import Queue, Event
from fastapi.testclient import TestClient
from light_map.vision.remote.remote_driver import create_app


def test_cors_default_restricted():
    """Verify that by default, CORS is restricted to common local origins."""
    results_queue = Queue()
    stop_event = Event()
    state_mirror = {}

    app = create_app(results_queue, stop_event, state_mirror)
    client = TestClient(app)

    # 1. Authorized origin (default)
    headers = {
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type",
    }
    response = client.options("/input/hands", headers=headers)
    assert response.status_code == 200
    assert (
        response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    )

    # 2. Unauthorized origin (default)
    headers = {
        "Origin": "http://evil.com",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type",
    }
    response = client.options("/input/hands", headers=headers)
    assert response.status_code == 400


def test_cors_restricted():
    """
    Verify that if we restrict origins, unauthorized ones are rejected.
    """
    results_queue = Queue()
    stop_event = Event()
    state_mirror = {}

    allowed = ["http://localhost:8000", "http://localhost:5173"]
    app = create_app(results_queue, stop_event, state_mirror, allowed_origins=allowed)
    client = TestClient(app)

    # 1. Authorized origin
    headers = {
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type",
    }
    response = client.options("/input/hands", headers=headers)
    assert response.status_code == 200
    assert (
        response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    )

    # 2. Unauthorized origin
    headers = {
        "Origin": "http://evil.com",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type",
    }
    response = client.options("/input/hands", headers=headers)

    # If CORS is restricted, Starlette CORSMiddleware returns 400 Bad Request for unauthorized preflight.
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
