import multiprocessing as mp
import time

import httpx
import pytest

from light_map.core.common_types import GestureType, ResultType
from light_map.vision.infrastructure.process_manager import VisionProcessManager


def test_remote_driver_e2e_mocked_loop():
    """
    Integration test:
    - Starts VisionProcessManager with RemoteDriverWorker.
    - Sends inputs via HTTP.
    - Verifies they arrive in the results queue.
    - Verifies state inspection reads from the shared mirror.
    """
    # 1. Setup Manager with Remote Driver enabled
    ctx = mp.get_context("spawn")
    manager_mp = ctx.Manager()
    state_mirror = manager_mp.dict()
    state_mirror["world"] = {"scene": "TEST"}

    # Use a high port to avoid conflicts
    port = 8081

    vm = VisionProcessManager(
        remote_mode_hands="exclusive", remote_port=port, state_mirror=state_mirror
    )

    # We need to mock CameraOperator because we don't have a real camera
    # But VisionProcessManager.start() creates it.
    # In a real CI, we might use a mock. Here let's just try to start it.
    # If it fails due to no camera, we might need to mock CameraOperator.

    # Let's mock CameraOperator.start to avoid hardware dependency
    from unittest.mock import MagicMock

    vm.operator = MagicMock()
    vm.operator.shm_name = "mock_shm"

    # Patch mp.Process to avoid starting actual vision workers that need SHM
    # We only want the RemoteDriverWorker.

    try:
        vm.start()

        # Wait for server to start
        base_url = f"http://127.0.0.1:{port}"
        for _ in range(50):
            try:
                resp = httpx.get(f"{base_url}/health")
                if resp.status_code == 200:
                    break
            except Exception:
                time.sleep(0.1)
        else:
            pytest.fail("Remote driver server failed to start")

        # 2. Test Input Injection
        hand_data = [{"x": 500, "y": 600, "gesture": "Pointing"}]
        resp = httpx.post(f"{base_url}/input/hands", json=hand_data)
        assert resp.status_code == 200

        # Drain queue
        result = vm.results_queue.get(timeout=2.0)
        assert result.type == ResultType.HANDS
        assert result.data[0].proj_pos == (500, 600)
        assert result.data[0].gesture == GestureType.POINTING

        # 3. Test State Inspection
        state_mirror["world"] = {"scene": "VIEWING", "fps": 59.9}
        resp = httpx.get(f"{base_url}/state/world")
        assert resp.status_code == 200
        assert resp.json()["scene"] == "VIEWING"

    finally:
        vm.stop()
