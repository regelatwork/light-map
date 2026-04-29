import httpx
import time
import subprocess
import os
import signal
import sys
import numpy as np
import socket as socket_lib
import tempfile
import shutil
import argparse
import json

def find_free_port():
    with socket_lib.socket(socket_lib.AF_INET, socket_lib.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]

def cleanup_old_resources():
    """Clean up leftover temp dirs and shared memory from previous runs."""
    import shutil
    import glob

    # 1. Clean /tmp and /var/tmp
    for pattern in ["/tmp/light_map_e2e_*", "/var/tmp/light_map_e2e_*"]:
        for path in glob.glob(pattern):
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
            except Exception as e:
                print(f"Warning: Could not clean up {path}: {e}")

    # 2. Clean Shared Memory (/dev/shm on Linux)
    if os.path.exists("/dev/shm"):
        for path in glob.glob("/dev/shm/light_map_*"):
            try:
                os.remove(path)
            except Exception as e:
                print(f"Warning: Could not clean up shared memory {path}: {e}")


def run_real_e2e(initial_config_dir=None, keep_on_failure=True, skip_ui=False):
    project_root = os.getcwd()
    python_bin = os.path.join(project_root, ".venv", "bin", "python3")
    
    print("Performing startup cleanup...")
    cleanup_old_resources()

    # 1. Setup isolated directories
    # We use a manual directory if we want to keep it on failure
    temp_base = tempfile.mkdtemp(prefix="light_map_e2e_")
    xdg_config = os.path.join(temp_base, "config")
    xdg_data = os.path.join(temp_base, "data")
    xdg_state = os.path.join(temp_base, "state")

    os.makedirs(os.path.join(xdg_data, "light_map"), exist_ok=True)
    os.makedirs(os.path.join(xdg_config, "light_map"), exist_ok=True)
    os.makedirs(os.path.join(xdg_state, "light_map"), exist_ok=True)

    # 2. Seed Initial Configuration if provided
    if initial_config_dir and os.path.exists(initial_config_dir):
        print(f"Seeding initial configuration from {initial_config_dir}...")
        # Copy config files to xdg_config/light_map
        for item in os.listdir(initial_config_dir):
            s = os.path.join(initial_config_dir, item)
            d = os.path.join(xdg_config, "light_map", item)
            if os.path.isfile(s):
                shutil.copy2(s, d)
            elif os.path.isdir(s):
                shutil.copytree(s, d, dirs_exist_ok=True)

    # 3. Prepare dummy calibration (only if not seeded)
    calib_path = os.path.join(xdg_data, "light_map", "projector_calibration.npz")
    if not os.path.exists(calib_path):
        np.savez(calib_path, projector_matrix=np.eye(3), resolution=[1920, 1080])
    
    cam_calib_path = os.path.join(xdg_data, "light_map", "camera_calibration.npz")
    if not os.path.exists(cam_calib_path):
        np.savez(cam_calib_path, camera_matrix=np.eye(3), dist_coeffs=np.zeros(5))
    
    cam_ext_path = os.path.join(xdg_data, "light_map", "camera_extrinsics.npz")
    if not os.path.exists(cam_ext_path):
        np.savez(cam_ext_path, rotation_vector=np.zeros(3), translation_vector=np.zeros(3))

    # 4. Find free ports
    backend_port = find_free_port()
    frontend_port = find_free_port()
    print(f"Using ports: Backend={backend_port}, Frontend={frontend_port}")
    print(f"Isolated Environment: {temp_base}")

    # 5. Start Backend
    log_file_path = os.path.join(xdg_state, "light_map", "backend_e2e.log")

    # We must allow the frontend's origin for CORS
    allowed_origins = [
        f"http://localhost:{frontend_port}",
        f"http://127.0.0.1:{frontend_port}"
    ]

    cmd = [
        python_bin, "-m", "light_map",
        "--remote-host", "127.0.0.1",
        "--remote-port", str(backend_port),
        "--remote-tokens", "exclusive",
        "--remote-hands", "exclusive",
        "--remote-origins"
    ] + allowed_origins + [
        "--map", "maps/test_blocker.svg",
        "--log-level", "DEBUG"
    ]
    env = os.environ.copy()
    env["MOCK_CAMERA"] = "1"
    env["PYTHONPATH"] = os.path.join(project_root, "src")
    env["XDG_CONFIG_HOME"] = xdg_config
    env["XDG_DATA_HOME"] = xdg_data
    env["XDG_STATE_HOME"] = xdg_state
    env["LIGHT_MAP_LOG_FILE"] = log_file_path

    print(f"Starting backend (logs: {log_file_path})...")
    print(f"Command: {' '.join(cmd)}")
    with open(log_file_path, "w") as log_file:
        backend_proc = subprocess.Popen(
            cmd, env=env, stdout=log_file, stderr=subprocess.STDOUT, text=True,
            bufsize=1 # Line buffered
        )

    base_url = f"http://127.0.0.1:{backend_port}"
    success = False
    
    try:
        # Wait for backend
        print("Waiting for backend to be ready...")
        ready = False
        for i in range(45): # Increased timeout
            # Check if process is still running
            if backend_proc.poll() is not None:
                print(f"Backend process EXITED prematurely with code {backend_proc.returncode}")
                break
            
            try:
                if httpx.get(f"{base_url}/health", timeout=1.0).status_code == 200:
                    ready = True
                    break
            except:
                pass
            time.sleep(1)
        
        if not ready:
            print("Backend failed to start. Logs:")
            if os.path.exists(log_file_path):
                with open(log_file_path, "r") as f:
                    print(f.read())
            return False

        # 6. Inject Tokens
        print("Injecting test tokens...")
        httpx.post(f"{base_url}/input/tokens", json=[
            {"id": 1, "x": 100.0, "y": 100.0, "z": 0.0},
            {"id": 2, "x": 200.0, "y": 100.0, "z": 0.0}
        ])

        # 7. Run Verification
        if skip_ui:
            print("Running Backend API Verification (skipping UI)...")
            # Wait for main loop to settle and calculate
            time.sleep(2)
            
            # Select token 1
            print("Selecting token 1...")
            sel_payload = json.dumps({"type": "TOKEN", "id": 1})
            resp = httpx.post(f"{base_url}/input/action", params={"action": "SET_SELECTION", "payload": sel_payload})
            if resp.status_code != 200:
                print(f"Error: SET_SELECTION failed with {resp.status_code}: {resp.text}")
                return False
            
            # Wait for calculation
            print("Waiting for tactical calculation...")
            time.sleep(3)
            
            # Check API
            print(f"Checking tactical cover API at {base_url}/tactical/cover?attacker_id=1")
            response = httpx.get(f"{base_url}/tactical/cover?attacker_id=1")
            if response.status_code != 200:
                print(f"Error: API returned {response.status_code}: {response.text}")
                return False
            
            data = response.json()
            print(f"Tactical Data: {json.dumps(data, indent=2)}")
            
            if "2" in data:
                print("SUCCESS: Tactical data retrieved via API!")
                success = True
            else:
                print("FAILURE: No tactical data for target '2' found in API response.")
                success = False
            
            return success
        else:
            print(f"Starting Playwright E2E on port {frontend_port}...")
        
        # CRITICAL: Clear Vite cache to ensure env vars are fresh
        vite_cache = os.path.join(project_root, "frontend", "node_modules", ".vite")
        if os.path.exists(vite_cache):
            print(f"Clearing Vite cache at {vite_cache}...")
            shutil.rmtree(vite_cache)

        frontend_origin = f"http://localhost:{frontend_port}"
        env["VITE_API_HOST"] = f"127.0.0.1:{backend_port}"
        env["PORT"] = str(frontend_port)
        
        # We need to restart the backend or have it allow the origin.
        # Since we haven't started Playwright yet, we know the origin.
        # But the backend was already started. 
        # Actually, let's just use 127.0.0.1 consistently.
        frontend_origin_alt = f"http://127.0.0.1:{frontend_port}"
        
        pw_cmd = [
            "npx", "playwright", "test", "e2e/tactical_real.spec.ts", 
            "--reporter=list"
        ]
        
        pw_proc = subprocess.run(
            pw_cmd, 
            cwd=os.path.join(project_root, "frontend"),
            env=env
        )
        
        success = (pw_proc.returncode == 0)
        
        if not success:
            print("Playwright tests failed.")
            print(f"Backend logs available at: {log_file_path}")
            
        return success

    finally:
        print("Shutting down backend...")
        backend_proc.terminate()
        try:
            backend_proc.wait(timeout=5)
        except:
            backend_proc.kill()

        if success or not keep_on_failure:
            print(f"Cleaning up isolated environment: {temp_base}")
            shutil.rmtree(temp_base)
        else:
            print(f"FAILURE DETECTED. Isolated environment PRESERVED for diagnosis: {temp_base}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run hermetic real frontend-to-backend E2E tests.")
    parser.add_argument("--config-dir", help="Directory containing initial configuration files to seed.")
    parser.add_argument("--no-keep", action="store_false", dest="keep", help="Delete isolated environment even on failure.")
    parser.add_argument("--skip-ui", action="store_true", help="Run backend-only verification (no browser).")
    parser.set_defaults(keep=True)
    
    args = parser.parse_args()
    
    result = run_real_e2e(initial_config_dir=args.config_dir, keep_on_failure=args.keep, skip_ui=args.skip_ui)
    sys.exit(0 if result else 1)
