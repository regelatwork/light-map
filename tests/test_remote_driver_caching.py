import os
import hashlib
import time
from multiprocessing import Queue, Event
from fastapi.testclient import TestClient
from light_map.vision.remote_driver import create_app
from light_map.core.storage import StorageManager

def test_map_svg_caching(tmp_path):
    results_queue = Queue()
    stop_event = Event()
    
    # Create a dummy map file
    map_path = tmp_path / "test_map.svg"
    map_path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"></svg>')
    
    state_mirror = {
        "config": {
            "current_map_path": str(map_path)
        }
    }

    app = create_app(results_queue, stop_event, state_mirror)
    client = TestClient(app)

    # Initial request
    response = client.get("/map/svg")
    assert response.status_code == 200
    etag = response.headers.get("ETag")
    assert etag is not None
    assert response.headers.get("Cache-Control") == "no-cache"

    # Conditional request (matching)
    response_match = client.get("/map/svg", headers={"If-None-Match": etag})
    assert response_match.status_code == 304

    # Modify file
    # We must ensure mtime changes. On some systems granularity is 1s.
    # Alternatively, we can manually set mtime if needed, but sleep is simpler for now.
    time.sleep(1.1)
    map_path.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200"></svg>')
    
    # Conditional request (after modification)
    response_changed = client.get("/map/svg", headers={"If-None-Match": etag})
    assert response_changed.status_code == 200
    new_etag = response_changed.headers.get("ETag")
    assert new_etag != etag

def test_map_fow_caching(tmp_path, monkeypatch):
    # Mock StorageManager data dir
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    sm = StorageManager()
    
    results_queue = Queue()
    stop_event = Event()
    
    map_path = "/tmp/fake_map.svg"
    stem = os.path.splitext(os.path.basename(map_path))[0]
    path_hash = hashlib.md5(map_path.encode()).hexdigest()[:8]
    fow_dir = os.path.join(sm.get_data_dir(), "fow", f"{stem}_{path_hash}")
    os.makedirs(fow_dir, exist_ok=True)
    fow_path = os.path.join(fow_dir, "fow.png")
    with open(fow_path, "wb") as f:
        f.write(b"fake_png_content")
        
    state_mirror = {
        "config": {
            "current_map_path": map_path
        }
    }

    app = create_app(results_queue, stop_event, state_mirror)
    client = TestClient(app)

    # Initial request
    response = client.get("/map/fow")
    assert response.status_code == 200
    etag = response.headers.get("ETag")
    assert etag is not None
    assert response.headers.get("Cache-Control") == "no-cache"

    # Conditional request (matching)
    response_match = client.get("/map/fow", headers={"If-None-Match": etag})
    assert response_match.status_code == 304

    # Modify file
    time.sleep(1.1)
    with open(fow_path, "wb") as f:
        f.write(b"modified_fake_png_content")
        
    # Conditional request (after modification)
    response_changed = client.get("/map/fow", headers={"If-None-Match": etag})
    assert response_changed.status_code == 200
    new_etag = response_changed.headers.get("ETag")
    assert new_etag != etag
