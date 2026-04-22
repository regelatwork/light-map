# Interactive App Refactor: Modular Orchestration

## Overview
This feature refactors the `InteractiveApp` from a monolithic "God Object" into a lean system bootstrapper and a suite of specialized, decoupled services. It establishes a strict architectural invariant for state management to ensure consistency and testability.

## Core Invariant: Read/Write Separation
To eliminate stale data bugs and race conditions, the application adheres to a strict access pattern for the `WorldState`:
- **Read-Only Access:** All downstream components (Scenes, Renderers, Remote API, Handlers) read state data exclusively from the `WorldState`.
- **Manager-Only Writes:** Only designated "Manager" or "Service" classes are authorized to mutate the `WorldState`. This is enforced through a **Writer Token** pattern: only classes initialized with a secret or registered as a manager can call state-mutating methods. Any external intent to change state must be routed through these managers for validation and persistence before the `WorldState` is updated.

## Architectural Components

### 1. The Bootstrapper (`InteractiveApp`)
- **Role:** High-level system lifecycle management.
- **Responsibilities:**
    - Initialize hardware (Camera, Projector).
    - Load initial configuration.
    - Set up Inter-Process Communication (IPC) and Shared Memory.
    - Spawn specialized processes (Vision, API).
    - Create and distribute **Tiered Contexts** (Main, Vision, Remote).
    - Graceful shutdown and resource cleanup.

### 2. The Shared State (`WorldState`)
- **Role:** The application's single source of truth.
- **Implementation:** Uses versioned "Atoms" to track changes.
- **Data:** Contains everything from token positions and map metadata to UI state and performance metrics.

### 3. The Managers (Main Process)
- **`SceneManager`**: A declarative state machine that handles scene transitions and provides the active layer stack to the renderer.
- **`EnvironmentManager`**: Coordinates visibility logic, converting token movements into Fog of War and Line-of-Sight updates.
- **`PersistenceService`**: Manages all file I/O (Maps, Sessions, Config). It validates incoming changes and ensures that disk state and `WorldState` remain synchronized.

## Tiered Contexts
To support multi-processing without serializing unnecessary objects, the app uses specialized contexts:
- **`MainContext`**: Full access to all services (Renderer, Managers, etc.).
- **`VisionContext`**: Stripped-down context (Config + Calibration) for worker processes.
- **`RemoteContext`**: Minimal context (Config + WorldState Ref) for the API bridge.

## Success Criteria
- `InteractiveApp.py` is reduced in size by ~60%.
- No business logic exists in `ActionDispatcher` handlers.
- `WorldState` mutations are traceable to a specific Manager call.
- All services are unit-testable without a full hardware stack or GUI.
