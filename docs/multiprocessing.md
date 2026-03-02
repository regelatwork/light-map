# Multiprocessing Architecture

Light Map uses a high-performance multi-process architecture to overcome Python's Global Interpreter Lock (GIL) limitations. This ensures that CPU-bound vision tasks (Hand Tracking, ArUco Detection) do not bottleneck the main application loop or the camera capture.

## Core Processes

1.  **Main Application Process**: Handles logic, state management, and rendering.
2.  **Camera Capture Process**: Dedicated to high-speed frame retrieval via GStreamer/OpenCV.
3.  **Vision Worker Processes**: Independent processes for Hand Landmarks and ArUco Token detection.

## Inter-Process Communication (IPC)

The system uses a combination of Shared Memory for high-resolution frames and `multiprocessing.Queue` for small detection results.

### Shared Memory ($N+2$ Buffer Strategy)

To ensure zero-copy frame sharing and prevent tearing, we use a single `multiprocessing.shared_memory.SharedMemory` block partitioned into a **Control Block** and **Frame Data**.

-   **$N$**: The number of consumer processes (e.g., HandDetector + ArUcoDetector).
-   **$N+2$ Guarantee**: We maintain $N+2$ buffers to guarantee that:
    -   $N$ buffers can be held by busy consumers.
    -   $1$ buffer is always available as the "latest" valid frame.
    -   $1$ buffer is always available for the Producer (`CameraOperator`) to write the next incoming frame.

#### Control Block Structure

-   **`ref_counts`**: Array of $N+2$ integers tracking active readers.
-   **`timestamps`**: Array of $N+2$ 64-bit integers (nanoseconds).
-   **`latest_buffer_id`**: Pointer to the most recent valid frame.
-   **`lock`**: Synchronizes access to the control block.

### Result IPC

Detectors push structured `DetectionResult` objects into dedicated `multiprocessing.Queue` instances. Each result contains:

-   **`timestamp`**: The timestamp of the camera frame used for detection.
-   **`type`**: The result category (e.g., `ARUCO`, `HANDS`).
-   **`data`**: The specific payload (coordinates, IDs, gestures).
-   **`metadata`**: Performance telemetry (hop timestamps).

## Key Components

### `VisionProcessManager` (Supervisor)
Runs in the Main Process and manages the lifecycle of all child processes. It allocates Shared Memory, spawns workers, monitors their health, and ensures clean teardown (`unlink()` of SHM).

### `CameraOperator` (Producer)
Runs in a dedicated process, capturing frames directly into Shared Memory segments following the $N+2$ strategy.

### `FrameProducer` (Consumer Interface)
An abstraction used by worker processes to safely access the most recent frame from Shared Memory via `get_latest_frame()` and `release()` semantics.

### `MainLoopController`
The heartbeat of the application. It polls result queues, updates `WorldState`, triggers the `InputManager` to map gestures/keys to `Action`s, and coordinates the active `Scene`.

## Data Flow

1.  **Camera** -> `CameraOperator` (SHM Write).
2.  **SHM** -> `Workers` (SHM Read via `FrameProducer`).
3.  **Workers** -> `ResultQueues` (IPC).
4.  **MainLoop** -> `WorldState` (Apply Results & ROI Extraction).
5.  **MainLoop** -> `Renderer` (Render to Projector).
