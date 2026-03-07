import httpx
import time
import subprocess
import os
import signal
import json


def verify():
    # 1. Determine project root (one level up from this script)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    os.chdir(project_root)

    # 2. Start the main application
    # We use --debug to get the performance report in the logs (every 5s)
    # We use --remote-hands exclusive to avoid issues with missing hardware camera for hands
    # We use --remote-tokens merge
    # We use --map to load a specific map
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
        "maps/grass-cave.svg",
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

        # 4. Stabilize and get initial state
        # Give the app time to finish its first few renders and stabilize
        time.sleep(10)
        resp = httpx.get(f"{base_url}/state/world")
        initial_state = resp.json()
        print(f"Initial State: {json.dumps(initial_state, indent=2)}")

        # 5. Verify Caching (Stable state)
        # Monitoring FPS in a stable state where no new frames should be rendered.
        print("Monitoring stable FPS for 5 seconds...")
        time.sleep(5)
        resp = httpx.get(f"{base_url}/state/world")
        stable_state = resp.json()
        print(f"Stable State FPS: {stable_state.get('fps')}")

        # 6. Trigger WorldState change (Simulate Token)
        # This should invalidate some caches (dynamic layers) and trigger at least one re-render.
        print("Injecting virtual token to trigger re-render...")
        token_data = [{"id": 42, "x": 100.0, "y": 100.0}]
        httpx.post(f"{base_url}/input/tokens", json=token_data)

        time.sleep(2)
        resp = httpx.get(f"{base_url}/state/world")
        after_token_state = resp.json()
        print(f"State after token: {json.dumps(after_token_state, indent=2)}")

        # 7. Inject Hand Gesture
        # Another way to trigger a "dirty" state without adding a token.
        print("Injecting hand gesture...")
        hand_data = [{"x": 500, "y": 500, "gesture": "Pointing"}]
        httpx.post(f"{base_url}/input/hands", json=hand_data)

        time.sleep(2)
        resp = httpx.get(f"{base_url}/state/world")
        after_hand_state = resp.json()
        print(f"State after hand: {json.dumps(after_hand_state, indent=2)}")

        # 8. Trigger Viewport change (MapLayer render)
        print("Zooming in to trigger MapLayer render...")
        httpx.post(f"{base_url}/map/zoom", params={"delta": 0.1})
        time.sleep(2)
        httpx.post(f"{base_url}/map/zoom", params={"delta": -0.1})
        time.sleep(2)

        # 9. Trigger Vision Actions
        print("Testing Vision Actions (SYNC_VISION, RESET_FOW)...")
        httpx.post(f"{base_url}/input/action", params={"action": "SYNC_VISION"})
        time.sleep(2)
        httpx.post(f"{base_url}/input/action", params={"action": "RESET_FOW"})
        time.sleep(2)

        # 10. Observe stability again and wait for Performance Statistics (logged every 10s)
        print("Waiting for final stability and performance report (approx 15s)...")
        time.sleep(15)

    finally:
        print("Stopping application...")
        # Send SIGINT (Ctrl+C) for graceful shutdown
        process.send_signal(signal.SIGINT)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()

        # Capture logs
        stderr_output = process.stderr.read()
        print("\n--- Application Logs (last 50 lines) ---")
        # Filter for the new Performance Statistics or RENDER TOTAL
        lines = stderr_output.splitlines()
        for line in lines[-50:]:
            if (
                "Performance Statistics" in line
                or "layer_render" in line
                or "RENDER TOTAL" in line
                or "renderer_composite" in line
            ):
                print(line)
            elif "INFO" in line or "DEBUG" in line:
                # Still show some context
                if len(line) > 150:
                    print(line[:150] + "...")
                else:
                    print(line)


if __name__ == "__main__":
    verify()
