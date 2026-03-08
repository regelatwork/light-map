from __future__ import annotations
import time
import logging
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from multiprocessing import Queue, Event

from light_map.common_types import DetectionResult, ResultType, Token, GestureType
from light_map.core.scene import HandInput


class RemoteHandInput(BaseModel):
    x: int
    y: int
    gesture: GestureType = GestureType.NONE


class RemoteWorldHandInput(BaseModel):
    world_x: float
    world_y: float
    gesture: GestureType = GestureType.NONE


class RemoteToken(BaseModel):
    id: int
    x: float
    y: float
    z: float = 0.0
    angle: float = 0.0


class ViewportConfig(BaseModel):
    zoom: Optional[float] = None
    pan_x: Optional[float] = None
    pan_y: Optional[float] = None
    rotation: Optional[float] = None


def create_app(results_queue: Queue, stop_event: Event, state_mirror: Dict[str, Any]):
    app = FastAPI(title="Light Map Remote Driver")

    @app.get("/health")
    def health():
        return {"status": "ok", "stop_event": stop_event.is_set()}

    @app.post("/input/hands")
    def inject_hands(hands: List[RemoteHandInput]):
        """Injects virtual hand inputs into the results queue."""
        processed_hands = []
        for h in hands:
            processed_hands.append(
                HandInput(
                    gesture=h.gesture,
                    proj_pos=(h.x, h.y),
                    unit_direction=(0.0, 0.0),  # Default to no specific direction
                    raw_landmarks=None,  # Virtual hands don't have landmarks
                )
            )

        res = DetectionResult(
            timestamp=time.monotonic_ns(),
            type=ResultType.HANDS,
            data=processed_hands,
        )
        results_queue.put(res)
        return {"status": "injected", "count": len(processed_hands)}

    @app.post("/input/hands/world")
    def inject_hands_world(hands: List[RemoteWorldHandInput]):
        """Injects virtual hand inputs using world coordinates."""
        hands_data = [
            h.model_dump() if hasattr(h, "model_dump") else h.dict() for h in hands
        ]
        res = DetectionResult(
            timestamp=time.monotonic_ns(),
            type=ResultType.ACTION,
            data={"action": "INJECT_HANDS_WORLD", "hands": hands_data},
        )
        results_queue.put(res)
        return {"status": "injected", "count": len(hands)}

    @app.post("/input/tokens")
    def inject_tokens(tokens: List[RemoteToken]):
        """Injects virtual ArUco tokens into the results queue."""
        processed_tokens = []
        for t in tokens:
            processed_tokens.append(
                Token(id=t.id, world_x=t.x, world_y=t.y, world_z=t.z, confidence=1.0)
            )

        # Wrapped as ARUCO result type
        res = DetectionResult(
            timestamp=time.monotonic_ns(),
            type=ResultType.ARUCO,
            data={"tokens": processed_tokens, "raw_tokens": processed_tokens},
        )
        results_queue.put(res)
        return {"status": "injected", "count": len(processed_tokens)}

    @app.post("/input/action")
    def inject_action(action: str, payload: Optional[str] = None):
        """Injects a manual application action (like SYNC_VISION)."""
        res = DetectionResult(
            timestamp=time.monotonic_ns(),
            type=ResultType.ACTION,
            data={"action": action, "payload": payload},
        )
        results_queue.put(res)
        return {"status": "injected", "action": action}

    @app.post("/map/zoom")
    def zoom_map(delta: float):
        """Injects a zoom action for the map system."""
        res = DetectionResult(
            timestamp=time.monotonic_ns(),
            type=ResultType.ACTION,
            data={"action": "ZOOM", "delta": delta},
        )
        results_queue.put(res)
        return {"status": "injected", "delta": delta}

    @app.post("/config/viewport")
    def set_viewport(config: ViewportConfig):
        data = {"action": "SET_VIEWPORT"}
        if config.zoom is not None:
            data["zoom"] = config.zoom
        if config.pan_x is not None:
            data["pan_x"] = config.pan_x
        if config.pan_y is not None:
            data["pan_y"] = config.pan_y
        if config.rotation is not None:
            data["rotation"] = config.rotation

        res = DetectionResult(
            timestamp=time.monotonic_ns(),
            type=ResultType.ACTION,
            data=data,
        )
        results_queue.put(res)
        return {"status": "injected"}

    @app.get("/config")
    def get_config():
        return state_mirror.get("config", {})

    @app.get("/state/menu")
    def get_menu_state():
        return state_mirror.get("menu", {})

    @app.get("/state/world")
    def get_world_state():
        return state_mirror.get("world", {})

    @app.get("/state/tokens")
    def get_tokens():
        return state_mirror.get("tokens", [])

    @app.get("/state/blockers")
    def get_blockers():
        return state_mirror.get("world", {}).get("blockers", [])

    @app.get("/state/dwell")
    def get_dwell():
        return state_mirror.get("world", {}).get("dwell_state", {})

    @app.get("/state/logs")
    def get_logs(lines: int = 100):
        try:
            from light_map.core.storage import StorageManager
            import os

            log_path = StorageManager().get_state_path("light_map.log")
            if not os.path.exists(log_path):
                return {"logs": []}
            with open(log_path, "r") as f:
                all_lines = f.readlines()
                return {"logs": [line.strip() for line in all_lines[-lines:]]}
        except Exception as e:
            return {"error": str(e)}

    @app.get("/state/clock")
    def get_clock():
        return {"time_monotonic": time.monotonic()}

    return app


def remote_driver_worker(
    results_queue: Queue,
    stop_event: Event,
    state_mirror: Dict[str, Any],
    port: int = 8000,
    host: str = "127.0.0.1",
):
    """Worker process entry point for the Remote Driver."""
    logging.info(f"Starting Remote Driver on {host}:{port}")
    app = create_app(results_queue, stop_event, state_mirror)

    config = uvicorn.Config(
        app, host=host, port=port, log_level="info", access_log=False
    )
    server = uvicorn.Server(config)

    # Run the server in the current process
    # We don't use server.run() because we might want to check stop_event
    # but uvicorn handles signals. For simplicity in a worker process:
    server.run()
