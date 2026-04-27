# Hermetic E2E Integration Testing

## 1. Goal
Provide a robust, repeatable, and isolated testing environment that verifies the full integration between the Web Dashboard (Frontend) and the Light Map Engine (Backend). This prevents "false positives" where mocked E2E tests pass while the real backend crashes or behaves unexpectedly.

## 2. Core Concepts

### 2.1 Full-Stack Verification
Unlike standard E2E tests that mock the network layer, Hermetic E2E tests run:
- A **real Backend process** (Python) in an isolated XDG environment.
- A **real Frontend dev server** (Vite) on a dynamic port.
- A **real Browser** (Playwright) connecting these two without any mocks.

### 2.2 Complete Isolation (Hermeticity)
To ensure tests are repeatable and don't interfere with the developer's local setup:
- **Temporary Directories:** Every test run creates a fresh temporary base directory (e.g., `/tmp/light_map_e2e_XXXXXX`).
- **Environment Overrides:** `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, and `XDG_STATE_HOME` are redirected to this temporary directory.
- **Port Randomization:** Both backend and frontend ports are dynamically selected to avoid conflicts with existing services.
- **Isolated Logging:** Backend logs are saved to a specific `backend_e2e.log` within the temporary directory.

### 2.3 Failure Diagnosis
To facilitate debugging when a full-stack integration fails:
- **Environment Preservation:** If a test fails, the isolated temporary directory is **not deleted**. This allows developers to inspect the generated `tokens.json`, calibration files, and logs.
- **Log Exposure:** The runner automatically prints the tail of the backend logs upon a failure to provide immediate context.

## 3. Technical Specifications

### 3.1 Runner Script (`scripts/run_real_frontend_e2e.py`)
The orchestrator responsible for:
1. Creating the isolated filesystem structure.
2. Seeding initial configuration (if provided via `--config-dir`).
3. Starting the backend via `xvfb-run` (to support headless environments).
4. Injecting initial test state (e.g., tokens) via the REST API.
5. Executing Playwright tests against the live servers.
6. Managing the lifecycle (startup/shutdown/cleanup) of all processes.

### 3.2 Configuration Seeding
Tests can be initialized with specific states by providing a directory of JSON/NPZ files.
```bash
python3 scripts/run_real_frontend_e2e.py --config-dir tests/e2e_configs/my_scenario/
```

## 4. Developer Workflow

### 4.1 Running the Integration Suite
To run the full integration suite:
```bash
./.venv/bin/python3 scripts/run_real_frontend_e2e.py
```

### 4.2 Debugging a Failure
1. Identify the preservation path in the output: `FAILURE DETECTED. Isolated environment PRESERVED: /tmp/light_map_e2e_abc123`.
2. Inspect `backend_e2e.log` in that directory to find Python tracebacks.
3. Check the `config/` and `data/` subdirectories to verify that the backend's internal state matches expectations.

## 5. Success Criteria
- **Zero Interference:** Running the test does not modify the developer's actual map sessions or calibration.
- **Crash Detection:** Any `AttributeError` or `ModuleNotFoundError` in the backend during a frontend interaction triggers a test failure.
- **End-to-End Latency:** The full cycle (setup, test, teardown) completes in under 30 seconds.
