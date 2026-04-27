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

def find_free_port():
    with socket_lib.socket(socket_lib.AF_INET, socket_lib.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]

def run_real_e2e(initial_config_dir=None, keep_on_failure=True):
    project_root = os.getcwd()
    python_bin = os.path.join(project_root, ".venv", "bin", "python3")
    
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
        "xvfb-run", "-a",
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
    with open(log_file_path, "w") as log_file:
        backend_proc = subprocess.Popen(
            cmd, env=env, stdout=log_file, stderr=subprocess.STDOUT, text=True
        )

    base_url = f"http://127.0.0.1:{backend_port}"
    success = False
    
    try:
        # Wait for backend
        print("Waiting for backend to be ready...")
        ready = False
        for i in range(30):
            try:
                if httpx.get(f"{base_url}/health").status_code == 200:
                    ready = True
                    break
            except:
                pass
            time.sleep(1)
        
        if not ready:
            print("Backend failed to start. Last 20 lines of logs:")
            if os.path.exists(log_file_path):
                with open(log_file_path, "r") as f:
                    print("".join(f.readlines()[-20:]))
            return False

        # 6. Inject Tokens
        print("Injecting test tokens...")
        httpx.post(f"{base_url}/input/tokens", json=[
            {"id": 1, "x": 100.0, "y": 100.0, "z": 0.0},
            {"id": 2, "x": 200.0, "y": 100.0, "z": 0.0}
        ])

        # 7. Run Playwright
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
    parser.set_defaults(keep=True)
    
    args = parser.parse_args()
    
    result = run_real_e2e(initial_config_dir=args.config_dir, keep_on_failure=args.keep)
    sys.exit(0 if result else 1)
