from __future__ import annotations
import time
import logging
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict, Any
from multiprocessing import Queue, Event

from light_map.common_types import DetectionResult, ResultType, Token, GestureType
from light_map.core.scene import HandInput


class RemoteHandInput(BaseModel):
    x: int
    y: int
    gesture: str = "None"


class RemoteToken(BaseModel):
    id: int
    x: float
    y: float
    z: float = 0.0
    angle: float = 0.0


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
            # Map string gesture to GestureType enum if possible, else use UNKNOWN or NONE
            try:
                g = GestureType(h.gesture)
            except ValueError:
                g = GestureType.UNKNOWN

            processed_hands.append(
                HandInput(
                    gesture=g,
                    proj_pos=(h.x, h.y),
                    unit_direction=(0.0, 0.0),  # Default to no specific direction
                    raw_landmarks=None,  # Virtual hands don't have landmarks
                )
            )

        res = DetectionResult(
            timestamp=time.perf_counter_ns(),
            type=ResultType.HANDS,
            data=processed_hands,
        )
        results_queue.put(res)
        return {"status": "injected", "count": len(processed_hands)}

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
            timestamp=time.perf_counter_ns(),
            type=ResultType.ARUCO,
            data={"tokens": processed_tokens, "raw_tokens": []},
        )
        results_queue.put(res)
        return {"status": "injected", "count": len(processed_tokens)}

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
