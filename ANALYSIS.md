# Project Analysis Report: Light Map

## 1. Code Style & Conventions

The codebase demonstrates a high level of maturity and adherence to modern Python standards.

- **Type Hinting:** Comprehensive use of `typing` (List, Optional, Tuple) and `dataclasses` ensures interfaces are clear and data structures are explicit. This significantly aids in static analysis and readability.
- **Formatting:** The code is clean and consistent, likely enforced by the `ruff` configuration mentioned in the documentation. Imports are organized, and indentation is uniform.
- **Naming:** Variable and function names are descriptive (`calculate_ppi_from_frame`, `detect_tokens`, `map_system`). Class names follow PascalCase, and variables/functions follow snake_case, adhering to PEP 8.
- **Data Structures:** The project effectively uses `dataclasses` (`Token`, `SessionData`, `ViewportState`) to manage state, avoiding "primitive obsession" (passing loose tuples/dicts around).
- **Error Handling:** There is some basic error handling (e.g., checking if `image is None`), but robust exception handling for file I/O or camera streams could be strengthened.

## 2. Code Organization & Architecture

The project employs a modular, component-based architecture that cleanly separates concerns.

### **Strengths:**

- **Logic Separation:**
  - **Core Logic:** `interactive_app.py` acts as the central controller/orchestrator, managing the application state machine (`AppMode`).
  - **Input Layer:** `input_manager.py` and `gestures.py` abstract raw MediaPipe data into semantic events, decoupling input hardware from game logic.
  - **Presentation Layer:** `renderer.py` handles UI drawing, while `svg_loader.py` handles map rendering.
  - **Domain Logic:** `map_system.py` encapsulates complex coordinate transformations (Screen \<-> World \<-> Grid), which is critical for an AR application.
- **Configuration Management:** separating `map_config.py` and `menu_config.py` allows for tuning without touching core logic.
- **Persistence:** `session_manager.py` and `SessionData` provide a clean serialization layer for saving/loading state.
- **Testing:** The `tests/` directory mirrors the source structure, with specific tests for offline tracking logic (`test_token_tracker_offline.py`), ensuring critical CV algorithms can be verified without a live camera.

### **Areas for Improvement:**

- **Hardcoded Values:** Some computer vision parameters (kernel sizes, threshold constants in `token_tracker.py`) are hardcoded. Moving these to a configuration file would allow for easier tuning in different lighting environments.
- **Coupling in `InteractiveApp`:** The `InteractiveApp` class is becoming a "God Object," handling input, state, rendering, and CV orchestration. Consider extracting the "Mode" logic (Menu vs. Map vs. Calibration) into separate "Scene" or "State" classes to reduce complexity.
- **Dependency Injection:** While `time_provider` is injected (good for testing), other components like `TokenTracker` or `SVGLoader` are instantiated directly inside `InteractiveApp`. Dependency injection could improve testability.

## 3. Future Feature Recommendations

Based on the current architecture and "reverted" features noted in `GEMINI.md`, here are technical recommendations for future expansion:

### **A. Robust Computer Vision (Addressing the "Interference" Issue)**

The project struggled with projection interference (projected light confusing the camera).

- **IR Tracking:** If hardware permits, switching to IR light/cameras would completely bypass visible light interference.
- **Structured Light / Temporal Encoding:** Projecting a specific pattern (or imperceptible high-freq flicker) to distinguish projected pixels from physical objects.
- **Machine Learning Classifiers:** Replace heuristic blob detection in `token_tracker.py` with a lightweight CNN (e.g., MobileNet) trained on *your* specific token dataset to better distinguish minis from shadows or hands.

### **B. Enhanced Mapping Features**

- **Fog of War:** With `svg_loader` and `map_system` already in place, implementing a dynamic mask layer to reveal/hide parts of the map based on token positions.
- **Dynamic Lighting:** Using the projector to cast "virtual shadows" or light sources based on the map's SVG geometry (walls blocking light).

### **C. Token Identity & Gameplay Integration**

- **Fiducial Markers:** Using ArUco markers on token bases would allow for unique IDs, enabling specific character tracking (e.g., "The Wizard moved," not just "A token moved").
- **Rules Engine Bridge:** Exporting token coordinates to a local API (WebSocket) to integrate with VTTs like Foundry or roll20, or a custom local rules engine.

### **D. User Experience (UX)**

- **Virtual "Touch" Surfaces:** Calibrating the table plane to detect "taps" (finger velocity/depth stops) rather than just "hover" gestures, making the UI feel more tactile.
- **Voice Control:** Integrating a lightweight offline speech recognition model (e.g., Vosk) for commands like "Save Session" or "Clear Map" to reduce reliance on complex hand gestures.
