import argparse
import subprocess
import time

import httpx


def main():
    parser = argparse.ArgumentParser(description="Drive the Light Map app via API")
    parser.add_argument("--map", default="maps/test_blocker.svg", help="SVG map path")
    parser.add_argument(
        "--tokens", type=int, nargs="+", default=[4, 11, 12], help="Token IDs to test"
    )
    parser.add_argument("--dwell", type=float, default=5.0, help="Dwell time per token")
    parser.add_argument(
        "--stabilize", type=float, default=5.0, help="Menu stabilization time"
    )
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="Base API URL")
    args = parser.parse_args()

    # 1. Start App
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
        args.map,
        "--log-level",
        "DEBUG",
    ]
    print(f"Starting app: {' '.join(cmd)}")
    process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

    try:
        # 2. Wait for API
        print("Waiting for API...")
        for _ in range(30):
            try:
                if httpx.get(f"{args.url}/health", timeout=1).status_code == 200:
                    print("API UP.")
                    break
            except Exception:
                time.sleep(1)
        else:
            return

        # 3. Stabilize via Menu
        print(f"Stabilizing (Menu for {args.stabilize}s)...")
        httpx.post(f"{args.url}/input/actions", json=["TRIGGER_MENU"])
        time.sleep(args.stabilize)
        httpx.post(f"{args.url}/input/actions", json=["TRIGGER_MENU"])
        time.sleep(2)

        # 4. Query & Select
        resp = httpx.get(f"{args.url}/state/tokens")
        detected = {t["id"]: (t["world_x"], t["world_y"]) for t in resp.json()}

        for tid in args.tokens:
            if tid in detected:
                wx, wy = detected[tid]
                print(f"Selecting Token {tid} at ({wx:.1f}, {wy:.1f})...")
                for _ in range(int(args.dwell * 2)):
                    httpx.post(
                        f"{args.url}/input/hands/world",
                        json=[
                            {
                                "world_x": wx,
                                "world_y": wy,
                                "gesture": "Pointing",
                                "unit_direction": {"x": 0, "y": 0, "z": 0},
                            }
                        ],
                    )
                    time.sleep(0.5)
            else:
                print(f"Token {tid} not detected.")

        # 5. Fetch Final Logs
        print("\n--- TACTICAL LOGS ---")
        logs = (
            httpx.get(f"{args.url}/state/logs", params={"lines": 50})
            .json()
            .get("logs", [])
        )
        for log in logs:
            if "[ExclusiveVision]" in log:
                print(log)

    finally:
        print("Shutting down...")
        try:
            httpx.post(f"{args.url}/input/actions", json=["QUIT"], timeout=2)
        except Exception:
            pass
        process.wait(timeout=5)


if __name__ == "__main__":
    main()
