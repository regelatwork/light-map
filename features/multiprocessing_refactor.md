# Feature Design: Multiprocessing Refactor

## Summary

Refactor the Light Map application from a threaded architecture to a multi-process architecture to overcome GIL-related performance bottlenecks. This design isolates CPU-bound vision tasks (Hand Tracking, ArUco Detection) and hardware IO (Camera) into dedicated processes, coordinated by a reactive, event-driven main loop.

## Background

The current threaded model in `CameraPipeline` and `InteractiveApp` suffers from significant latency and low frame rates when multiple vision detectors are active. Because Python's Global Interpreter Lock (GIL) prevents true parallel execution of CPU-bound tasks, the system cannot effectively utilize multi-core processors. Performance issue `bd-3hw` highlights hand tracking dropping below 1 FPS with latency exceeding 1 second, necessitating a move to `multiprocessing`.

## Design Summary

The system will be split into four primary process types:

1. **Camera Capture Process**: Dedicated to high-speed frame retrieval.
1. **Vision Detection Processes**: Separate processes for Hand Landmarks and ArUco Tokens.
1. **Main Application Process**: Handles logic, state management, and rendering.

**IPC Strategy**:

- **Frames**: Shared Memory (via `multiprocessing.shared_memory`) in a circular buffer to avoid expensive serialization of raw images.
- **Results**: `multiprocessing.Queue` for small detection results (coordinates, IDs, gestures).
- **Synchronization**: Atomic shared counters for frame indices and a reactive event loop in the main process.

## Detailed Design

### Class: CameraOperator

- **Role**: Hardware/GStreamer Producer.
- **Responsibilities**:
  - Manages the camera lifecycle (Open/Close).
  - Allocates a Shared Memory block for a circular buffer of $N$ frames.
  - Captures frames and writes them into the buffer.
  - Updates an atomic `latest_index` and `timestamp` in a small control block in shared memory.

### Class: FrameProducer

- **Role**: IPC Abstraction for Consumers.
- **Responsibilities**:
  - Initialized with an ID to track which consumer is accessing the frames.
  - Provides `get_latest_frame()`: Returns the most recent frame and its timestamp from shared memory without copying (using `numpy.ndarray` views where possible).
  - Provides `release()`: Signals that the consumer is done with the frame (important for managing buffer contention in more complex ring-buffer implementations).
  - Hides the underlying shared memory complexity from the detectors and renderer.

### Class: VisionProcessManager

- **Role**: Process Orchestrator.
- **Responsibilities**:
  - Acts as the "Supervisor" in the Main Process.
  - Sets up the `CameraOperator` and Shared Memory.
  - Spawns child processes for `HandDetector` and `ArucoDetector`.
  - Monitors process health and restarts workers if necessary.
  - Ensures clean teardown, specifically unlinking shared memory segments to prevent memory leaks on the OS.

### Class: WorldState

- **Role**: Central Data Repository (The "Source of Truth").
- **Responsibilities**:
  - Stores a snapshot of the world: token list, hand data, active menu, viewport, and notifications.
  - Implements a `dirty` flag logic: If an update significantly changes the state (e.g., token moves past a threshold), it marks itself as needing a redraw.
  - Provides a thread-safe `apply(event)` method to ingest data from various sources.

### Class: TemporalEventManager

- **Role**: Time-Based Event Scheduler.
- **Responsibilities**:
  - Allows the application to schedule "Alerts" or state mutations in the future (e.g., "Clear notification in 2 seconds").
  - Maintains a sorted list of upcoming events.
  - Provides a non-blocking check for expired events to the main loop.

### Class: MainLoopController

- **Role**: System Heartbeat & Event Aggregator.
- **Responsibilities**:
  - Encapsulates the waiting/polling strategy (e.g., high-frequency polling at a configurable 30Hz).
  - Aggregates events from Vision Queues, Keyboard input, and the `TemporalEventManager`.
  - Orchestrates the update-then-render cycle based on `WorldState`'s dirty flag.

### Class: HandDetectorProcess / ArucoDetectorProcess

- **Role**: CPU Workers.
- **Responsibilities**:
  - Uses a `FrameProducer` to pull the latest available frame.
  - Executes the respective vision algorithm (MediaPipe or OpenCV ArUco).
  - Pushes results into an outbound `multiprocessing.Queue`.
  - Drops frames if the previous processing task is still running to ensure zero "lag" on the results.

## IPC and Data Flow

1. **CameraOperator** writes Frame $K$ to Shared Memory.
1. **Detectors** poll their `FrameProducer` for the latest index. If $K > last_processed$, they begin work.
1. **Detectors** push `Result(K)` to their Results Queue.
1. **MainLoopController** drains the queues. It applies the newest results to the **WorldState**.
1. **MainLoopController** checks for Key events and Temporal events, applying them to **WorldState**.
1. If **WorldState** is "dirty", the **Renderer** is invoked to update the projector output.

## Appendix: Alternatives Considered

### 1. Queues for Frames

- **Pros**: Easy to implement, no shared memory management.
- **Cons**: Severe performance penalty due to Python's `pickle` serialization of large numpy arrays (the frame must be copied multiple times between processes). Rejected in favor of Shared Memory.

### 2. Global "Remote Driver" Architecture (WebDriver style)

- **Pros**: Extreme decoupling; vision system can run on a different machine.
- **Cons**: High complexity and latency introduced by network/socket overhead.
- **Decision**: Deferred as a future evolution. The current design uses a local `VisionProcessManager` to maintain simplicity while keeping interfaces clean enough to transition to a remote driver later.

### 3. Waiting vs Polling for Events

- **Wait (select/epoll)**: More power-efficient but difficult to coordinate with OpenCV's GUI/Key polling and custom Temporal Events.
- **Polling (High-Frequency)**: Simple, predictable latency, and easy to implement.
- **Decision**: Use High-Frequency Polling (configurable 30-60Hz) as the default strategy.
