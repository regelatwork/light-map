# Design Document: Remote Application Driver (Light-Map WebDriver)

**Date:** 2026-03-02  
**Status:** Validated  
**Epic:** `bd-1bu`

## 1. Overview

The Remote Application Driver (Light-Map WebDriver) enables remote control, automated testing, and state introspection of the Light Map application. By providing an HTTP/WebSocket interface, it allows external scripts and agents (like Gemini) to simulate user inputs (hand gestures, token movements) and query the application's internal state without physical hardware.

## 2. Goals

- **Automated Testing:** Enable deterministic playback of interaction sequences.
- **Remote Diagnosis:** Allow agents to "see" the internal state (menu regions, configurations) to diagnose issues.
- **Distributed Execution:** Support running vision processing or control logic on separate machines.
- **Headless Operation:** Support running the application logic and rendering without a physical camera.

## 3. Architecture

The Remote Driver operates as a dedicated process within the existing multi-process vision architecture.

### 3.1 Process Model

- **RemoteDriverProcess:** A separate `multiprocessing.Process` that hosts a FastAPI/Uvicorn server.
- **Input Bridge:** The process pushes `DetectionResult` objects into the shared `results_queue` used by the `MainLoopController`.
- **State Mirror:** A `multiprocessing.Manager().dict()` provides a shared, synchronized proxy for the Main Process to publish state updates (e.g., menu regions, viewport) that the Remote Driver can serve via `GET` requests.

### 3.2 Input Policies

Input modes are configured at startup via CLI flags:

- `--remote-hands [exclusive|merge|ignore]`
- `--remote-tokens [exclusive|merge|ignore]`

| Mode | Behavior |
| :--- | :--- |
| **exclusive** | Physical worker is NOT started; only Remote Driver inputs are accepted. |
| **merge** | Both physical worker and Remote Driver push to the queue. |
| **ignore** | Remote Driver inputs for this type are discarded (or the endpoint returns 403). |

## 4. API Specification

### 4.1 Input Injection (POST)

- `POST /input/hands`: Injects virtual hand landmarks and gestures.
- `POST /input/tokens`: Injects virtual ArUco tokens (ID, world coordinates).

### 4.2 State Introspection (GET)

- `GET /config`: Returns `AppConfig` (Resolution, PPI, Distortion Model, Token Config).
- `GET /state/menu`: Returns active menu hierarchy and pixel-perfect bounding boxes for all items.
- `GET /state/world`: Returns a snapshot of `WorldState` (Active Scene, Viewport, Notifications).
- `GET /state/tokens`: Returns currently detected tokens.

## 5. Implementation Details

- **Tech Stack:** FastAPI, Uvicorn, Pydantic (for schema validation).
- **Synchronization:** `multiprocessing.Manager().dict()` for the state mirror (updated every tick by the Main Process).
- **Serialization:** Standard JSON for all API communication.

## 6. Verification Plan

- **Unit Tests:** Verify FastAPI endpoint logic and `DetectionResult` wrapping.
- **Integration Tests:** Use `pytest` to start the app in `exclusive` mode and verify that `POST` requests trigger the expected `WorldState` mutations and rendering updates.
- **End-to-End:** Perform a "Remote Menu Navigation" test where a script queries `/state/menu`, calculates a coordinate, and sends a `POST /input/hands` "pinch" to trigger a menu action.
