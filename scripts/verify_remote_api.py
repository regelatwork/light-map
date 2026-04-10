import httpx
import time
import subprocess
import os
import signal
import json


def verify_remote_api():
    # 1. Determine project root
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    os.chdir(project_root)

    # 2. Start the main application
    cmd = [
        "python3",
        "-m",
        "light_map",
        "--debug",
        "--remote-hands",
        "exclusive",
        "--remote-tokens",
        "merge",
        "--map",
        "maps/test_blocker.svg",
        "--log-level",
        "DEBUG",
    ]

    print(f"Starting application from {project_root}: {' '.join(cmd)}")
    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )

    base_url = "http://127.0.0.1:8000"

    try:
        # 3. Wait for API to be ready
        print("Waiting for Remote Driver API...")
        for _ in range(30):
            try:
                resp = httpx.get(f"{base_url}/health", timeout=1)
                if resp.status_code == 200:
                    print("API is UP.")
                    break
            except Exception:
                time.sleep(1)
        else:
            print("Timed out waiting for API.")
            return

        time.sleep(5)  # Stabilization

        # 4. Check /state/clock
        resp = httpx.get(f"{base_url}/state/clock")
        print(f"Clock Sync: {resp.json()}")
        assert "time_monotonic" in resp.json()

        # 5. Check /state/blockers
        resp = httpx.get(f"{base_url}/state/blockers")
        blockers = resp.json()
        print(f"Found {len(blockers)} blockers.")
        if blockers:
            print(f"Sample Blocker: {json.dumps(blockers[0], indent=2)}")

        # 6. Check /config/viewport
        print("Setting explicit viewport...")
        viewport_data = {"zoom": 1.5, "x": 10.0, "y": 10.0}
        resp = httpx.post(f"{base_url}/config/viewport", json=viewport_data)
        assert resp.status_code == 200

        time.sleep(1)
        resp = httpx.get(f"{base_url}/state/world")
        world = resp.json()
        print(f"Viewport after SET: {world.get('viewport')}")

        # 7. Check /input/hands/world
        # Target the first blocker if available
        if blockers:
            target_x, target_y = blockers[0]["points"][0]
            print(f"Injecting hand at world coordinate: ({target_x}, {target_y})")
            hand_data = [
                {"world_x": target_x, "world_y": target_y, "gesture": "Pointing"}
            ]
            resp = httpx.post(f"{base_url}/input/hands/world", json=hand_data)
            assert resp.status_code == 200

            # 8. Check /state/dwell
            # Dwell might take time to accumulate, but let's see if we see it starting
            print("Checking dwell state...")
            time.sleep(0.5)
            resp = httpx.get(f"{base_url}/state/dwell")
            print(f"Dwell State: {json.dumps(resp.json(), indent=2)}")

        # 9. Check /state/tokens (screen coordinates)
        print("Injecting virtual token...")
        token_data = [{"id": 99, "x": 50.0, "y": 50.0}]
        httpx.post(f"{base_url}/input/tokens", json=token_data)
        time.sleep(1)

        resp = httpx.get(f"{base_url}/state/tokens")
        tokens = resp.json()
        if tokens:
            print(f"Token with screen coords: {json.dumps(tokens[0], indent=2)}")
            assert "screen_x" in tokens[0]
            assert "screen_y" in tokens[0]

            # Inject hand at token position to trigger dwell on token
            print("Injecting hand at token world coordinate: (50.0, 50.0)")
            hand_data = [{"world_x": 50.0, "world_y": 50.0, "gesture": "Pointing"}]
            httpx.post(f"{base_url}/input/hands/world", json=hand_data)
            time.sleep(1)
            resp = httpx.get(f"{base_url}/state/dwell")
            print(f"Dwell State on Token: {json.dumps(resp.json(), indent=2)}")

        # 10. Check /state/logs
        print("Fetching logs...")
        resp = httpx.get(f"{base_url}/state/logs", params={"lines": 10})
        logs = resp.json().get("logs", [])
        print(f"Fetched {len(logs)} log lines.")
        if logs:
            print(f"Last log: {logs[-1]}")

    finally:
        print("Stopping application...")
        process.send_signal(signal.SIGINT)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


if __name__ == "__main__":
    verify_remote_api()
