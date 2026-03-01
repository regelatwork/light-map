# Design Document: Multiprocessing Refactor (Vision & Input)

**Date**: 2026-02-28
**Status**: Validated
**Related**: `features/multiprocessing_refactor.md`, `docs/plans/2026-03-01-multiprocessing-ipc-design.md`

## Overview

This document defines the high-level architecture for the Light Map multiprocessing refactor, specifically focusing on the `WorldState`, `InputManager`, and the coordination between vision workers and the `MainProcess`.

## 1. WorldState & Background ROI Management

The `WorldState` serves as the central synchronization point for the `MainProcess`. Instead of holding a lease on a large shared memory buffer, it maintains a **local, cropped copy** of the relevant camera area (the "Map ROI"). This minimizes shared memory contention and allows the `CameraOperator` to reuse buffers as quickly as possible.

### Key Responsibilities
- **Local Storage**: Holds a `numpy.ndarray` of the extracted background and a `last_frame_timestamp`.
- **Functional Injection**: Upon initialization, it receives a `frame_processor` callable (e.g., `renderer.extract_map_roi`).
- **Update Logic**: The `update_from_frame(shm_view, timestamp)` method:
    1. Executes the injected `frame_processor(shm_view)`.
    2. Updates its internal background buffer with the result.
    3. Sets a granular `dirty_background` flag to `True`.
    4. Records the `timestamp` to ensure synchronization with vision results.

## 2. Result IPC & Event Aggregator

To coordinate vision results from separate processes (Hand Tracking, ArUco Detection) with the `MainProcess`, we use **Result IPC** based on `multiprocessing.Queue`. Each detector process pushes structured `DetectionResult` objects into its dedicated queue.

### Event Schema
A `DetectionResult` contains:
- **`timestamp`**: The timestamp of the camera frame used for this detection.
- **`type`**: The category of result (e.g., `ARUCO_UPDATE`, `GESTURE_EVENT`).
- **`data`**: The specific payload (e.g., a list of token IDs and their coordinates, or hand landmarks).

### MainLoop Aggregation
The `MainLoopController` polls these queues at a high frequency (e.g., 60Hz):
1. **Drains Queues**: Pulls all available results from the Hand and ArUco queues.
2. **State Application**: Calls `world_state.apply(result)` for each item.
3. **Synchronization**: `WorldState` uses the `timestamp` to ensure it only applies results that are newer than its current state.
4. **Dirty Flagging**: As `WorldState` updates its data, it sets granular flags (e.g., `dirty_tokens = True`).

## 3. Process Supervision & Shared Memory Lifecycle

The **`VisionProcessManager`** acts as the system supervisor, running within the `MainProcess`.

### Shared Memory Lifecycle
- **Initialization**: Allocates a `multiprocessing.shared_memory.SharedMemory` block partitioned into a Control Block and Frame Data.
- **Worker Management**: Spawns all child processes and passes them the SHM segment name.
- **Health Monitoring**: Non-blocking `is_alive()` checks used by the `MainLoopController`.
- **Cleanup**: Critical `shm.unlink()` call during `stop()` to prevent memory leaks on Linux.

## 4. Unified Input Management & Scene Dispatch

The `InputManager` translates raw hardware and vision events into high-level, semantic **"Actions"**.

### Unified Input Proxy
- **Hardware**: Captures keyboard input via `cv2.waitKey(1)`.
- **Vision**: Retrieves recent gesture detections from the `WorldState`.
- **Semantic Mapping**: Translates raw inputs (e.g., `Key.ENTER` or `Gesture.PINCH`) into `Action.SELECT`.

### Context-Aware Dispatch
The `MainLoopController` retrieves the pending `Action` list and dispatches it to the **Active Scene** (e.g., `MapScene.handle_input(actions)`). The scene decides the specific meaning of each action based on its internal state.

## 5. Data Flow & Testing Strategy

### Data Flow
1. **Camera** -> `CameraOperator` (SHM Write).
2. **SHM** -> `Detectors` (SHM Read via `FrameProducer`).
3. **Detectors** -> `ResultQueues` (IPC).
4. **MainLoop** -> `WorldState` / `InputManager`.
5. **WorldState** -> `Renderer` (via `dirty` flags).

### Testing Strategy
- **Unit Tests**: Isolation testing of `FrameProducer`, `WorldState`, and `InputManager`.
- **Integration Tests**: "Playback" detectors reading from files to verify the `MainLoop` and `WorldState` logic.
- **Benchmarking**: "Glass-to-Glass" latency measurement utility.
