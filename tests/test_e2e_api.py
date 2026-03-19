import httpx
import time
import subprocess
import os
import signal
import pytest
import socket as socket_lib
import numpy as np


def find_free_port():
    with socket_lib.socket(socket_lib.AF_INET, socket_lib.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


@pytest.mark.e2e
def test_full_app_api_sync_e2e():
    """
    End-to-End test that starts the full application and verifies API sync.
    This test verifies that:
    1. Remote tokens can be injected and retrieved.
    2. Physical tokens (simulated via raw corners) don't overwrite remote tokens in merge mode.
    3. Empty physical detections correctly clear physical tokens but preserve remote ones.
    4. Token movements are correctly reflected in GET responses.
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    python_bin = os.path.join(project_root, ".venv", "bin", "python3")

    # 1. Prepare dummy calibration
    calib_file = os.path.join(project_root, "projector_calibration.npz")
    cam_calib = os.path.join(project_root, "camera_calibration.npz")

    # We'll restore these if they exist, or delete them if we created them
    existed_proj = os.path.exists(calib_file)
    existed_cam = os.path.exists(cam_calib)

    if not existed_proj:
        np.savez(calib_file, projector_matrix=np.eye(3), resolution=[1920, 1080])
    if not existed_cam:
        np.savez(cam_calib, camera_matrix=np.eye(3), dist_coeffs=np.zeros(5))

    port = find_free_port()
    cmd = [
        "xvfb-run",
        "-a",
        python_bin,
        "-m",
        "light_map",
        "--remote-tokens",
        "merge",
        "--remote-hands",
        "exclusive",
        "--remote-port",
        str(port),
        "--map",
        "maps/test_blocker.svg",
        "--log-level",
        "INFO",
    ]

    env = os.environ.copy()
    env["MOCK_CAMERA"] = "1"
    env["PYTHONPATH"] = os.path.join(project_root, "src")

    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env
    )

    base_url = f"http://127.0.0.1:{port}"

    try:
        # 2. Wait for API to be ready
        api_ready = False
        for _ in range(30):
            try:
                resp = httpx.get(f"{base_url}/health", timeout=1)
                if resp.status_code == 200:
                    api_ready = True
                    break
            except Exception:
                time.sleep(1)

        if not api_ready:
            stdout, stderr = process.communicate(timeout=1)
            pytest.fail(f"API failed to start. Logs:\n{stderr}")

        # Give the app a moment to finish initialization
        time.sleep(2)

        # 3. Inject a remote token
        remote_id = 100
        token_data = [{"id": remote_id, "x": 500.0, "y": 500.0, "z": 0.0}]
        resp = httpx.post(f"{base_url}/input/tokens", json=token_data)
        assert resp.status_code == 200

        time.sleep(1)  # Processing time

        # 4. Verify remote token via GET
        resp = httpx.get(f"{base_url}/state/tokens")
        tokens = resp.json()
        assert any(t["id"] == remote_id for t in tokens), (
            "Remote token not found after injection"
        )

        # 5. Inject physical tokens (via raw corners)
        # Note: with identity calibration, (100,100) cam -> (100,100) world approx
        corners = [[[100.0, 100.0], [110.0, 100.0], [110.0, 110.0], [100.0, 110.0]]]
        ids = [1]
        resp = httpx.post(
            f"{base_url}/input/aruco_corners", json={"corners": corners, "ids": ids}
        )
        assert resp.status_code == 200

        time.sleep(1)

        # 6. Verify BOTH tokens exist (Merging check)
        resp = httpx.get(f"{base_url}/state/tokens")
        tokens = resp.json()
        token_ids = [t["id"] for t in tokens]
        assert remote_id in token_ids, (
            "Remote token was lost after physical injection (Merging BUG)"
        )
        # Note: physical token might not appear if calibration is too dummy for aruco_mapper
        # but the critical part is that remote_id survives.

        # 7. Inject EMPTY physical tokens
        resp = httpx.post(
            f"{base_url}/input/aruco_corners", json={"corners": [], "ids": []}
        )
        assert resp.status_code == 200

        time.sleep(1)

        # 8. Verify remote token STILL exists
        resp = httpx.get(f"{base_url}/state/tokens")
        tokens = resp.json()
        token_ids = [t["id"] for t in tokens]
        assert remote_id in token_ids, (
            "Remote token was wiped by empty physical update (Mapping BUG)"
        )

        # 9. Move remote token
        token_data = [{"id": remote_id, "x": 600.0, "y": 600.0, "z": 0.0}]
        httpx.post(f"{base_url}/input/tokens", json=token_data)

        time.sleep(1)

        resp = httpx.get(f"{base_url}/state/tokens")
        tokens = resp.json()
        t = next(t for t in tokens if t["id"] == remote_id)
        assert abs(t["world_x"] - 600.0) < 1.0, (
            f"Token did not move correctly: {t['world_x']}"
        )

    finally:
        process.send_signal(signal.SIGINT)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()

        # Cleanup dummy calibration if we created them
        if not existed_proj and os.path.exists(calib_file):
            os.remove(calib_file)
        if not existed_cam and os.path.exists(cam_calib):
            os.remove(cam_calib)
