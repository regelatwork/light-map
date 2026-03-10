# Extend Remote Driver Implementation Plan

> **For Gemini:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable the `Remote Driver` (FastAPI) to serve the built React frontend and broadcast real-time state updates via WebSockets.

**Architecture:** Use `fastapi.staticfiles.StaticFiles` for serving assets and a robust `ConnectionManager` to manage active WebSocket clients for state broadcasting.

**Tech Stack:** FastAPI, WebSockets, Python `asyncio`.

---

### Task 1: Implement WebSocket Connection Manager

**Files:**
- Modify: `src/light_map/vision/remote_driver.py`

**Step 1: Write the `ConnectionManager` class**
Add to `src/light_map/vision/remote_driver.py` with logging and robust disconnect handling.
```python
from fastapi import WebSocket
import logging

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logging.info(f"WebSocket client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logging.info(f"WebSocket client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        # Iterate over a copy to allow safe removal during iteration
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)
```

**Step 2: Initialize manager and add WebSocket endpoint**
Modify `create_app` in `src/light_map/vision/remote_driver.py` to include the `/ws/state` endpoint.
```python
manager = ConnectionManager()

@app.websocket("/ws/state")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection open, handle incoming heartbeat/messages
            await websocket.receive_text()
    except Exception:
        manager.disconnect(websocket)
```

**Step 3: Commit**
Run: `git add src/light_map/vision/remote_driver.py && git commit -m "feat(remote-driver): add websocket connection manager and endpoint"`

---

### Task 2: Implement State Broadcast Loop

**Files:**
- Modify: `src/light_map/vision/remote_driver.py`

**Step 1: Add background task for state broadcasting**
Modify `create_app` to start an `asyncio` task on startup that broadcasts `state_mirror` updates at ~30Hz.
```python
import asyncio

@app.on_event("startup")
async def startup_event():
    async def broadcast_loop():
        logging.info("Starting WebSocket state broadcast loop.")
        while not stop_event.is_set():
            if manager.active_connections:
                state = {
                    "world": state_mirror.get("world", {}),
                    "tokens": state_mirror.get("tokens", []),
                    "menu": state_mirror.get("menu", {}),
                    "timestamp": time.monotonic(),
                }
                await manager.broadcast(state)
            await asyncio.sleep(0.033) # ~30Hz
        logging.info("WebSocket state broadcast loop stopped.")

    asyncio.create_task(broadcast_loop())
```

**Step 2: Commit**
Run: `git add src/light_map/vision/remote_driver.py && git commit -m "feat(remote-driver): add state broadcast background task"`

---

### Task 3: Serve Static Frontend Assets

**Files:**
- Modify: `src/light_map/vision/remote_driver.py`

**Step 1: Mount StaticFiles (MUST BE LAST)**
Modify `create_app` to serve the `frontend/dist` directory. Ensure it's mounted after all other API routes to avoid path conflicts.
```python
from fastapi.staticfiles import StaticFiles
import os

# At the VERY END of create_app, before returning the app
frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../frontend/dist"))
if os.path.exists(frontend_dist):
    # html=True ensures index.html is served for the root path
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
else:
    logging.warning(f"Frontend dist directory not found at {frontend_dist}. Dashboard UI will not be available.")
```

**Step 2: Commit**
Run: `git add src/light_map/vision/remote_driver.py && git commit -m "feat(remote-driver): serve frontend static assets"`

---

### Task 4: Verification (TDD)

**Files:**
- Create: `tests/test_remote_driver_ws.py`

**Step 1: Write WebSocket integration test**
Use `TestClient(app).websocket_connect("/ws/state")` to verify that the endpoint broadcasts data and handles state changes from `state_mirror`.

**Step 2: Run tests**
Run: `pytest tests/test_remote_driver_ws.py -v`
Expected: PASS.

**Step 3: Commit**
Run: `git add tests/test_remote_driver_ws.py && git commit -m "test(remote-driver): add websocket broadcast integration test"`
