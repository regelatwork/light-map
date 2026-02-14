# Tests

This directory contains unit tests for the Light Map project.

## Running Tests

Tests are run using [pytest](https://docs.pytest.org/).

### Prerequisites

Ensure you have the development dependencies installed:

```bash
pip install pytest ruff
```

### Run all tests

From the project root, run:

```bash
pytest
```

### Run a specific test file

```bash
pytest tests/test_camera.py
```

## Configuration

The project uses a `src` layout. Pytest is configured via `pytest.ini` in the project root to:

1. Add `src` to the `pythonpath` so that `light_map` is importable.
1. Set `tests` as the default test directory.

## Test Coverage

The following components are covered by unit tests:

- **`test_camera.py`**: Mocks OpenCV to verify camera initialization, frame reading, and context management.
- **`test_calibration.py`**: Tests camera calibration logic, including chessboard corner detection and image loading.
- **`test_calibration_logic.py`**: Tests the high-level projector calibration sequence and hardware orchestration.
- **`test_gestures.py`**: Verifies the heuristic-based hand gesture recognition (Open Palm, Victory, Gun, etc.).
- **`test_input_manager.py`**: Tests input smoothing, sticky hand tracking, and flicker recovery.
- **`test_interactive_app.py`**: Tests the main application orchestrator, including coordinate transformation and gesture processing.
- **`test_menu_system.py`**: Tests the hierarchical menu state machine, navigation, and selection logic.
- **`test_projector.py`**: Tests calibration pattern generation and homography computation.
- **`test_renderer.py`**: Verifies that the menu UI renders correctly onto a BGR image.
- **`test_svg_loader.py`**: Tests SVG parsing and rendering into OpenCV images using `svgelements`.
- **`test_map_system.py`**: Verifies map viewport logic (pan, pinned zoom, rotation).
- **`test_map_config.py`**: Tests JSON persistence for map settings and calibration.
- **`test_calibration_logic_ppi.py`**: Tests Projector PPI detection from printed ArUco markers.
- **`test_svg_loader_image.py`**: Tests rendering of SVGs with embedded raster images and fills.
- **`test_svg_loader_paths.py`**: Tests rendering of discontinuous SVG paths (e.g., handling Move commands).
- **`test_camera_pipeline.py`**: Tests the multi-threaded camera processing pipeline.
- **`test_svg_loader_performance.py`**: Tests dynamic resolution rendering and caching performance.
- **`test_renderer_dimming.py`**: Verifies map opacity rendering (dimming/hiding) for UI interference mitigation.
- **`test_menu_sticky_selection.py`**: Tests the "sticky" menu selection logic where the last hovered item remains selected.
- **`test_menu_config_structure.py`**: Verifies the hierarchical menu structure definition (Root, Submenus, Actions).
- **`test_menu_pagination.py`**: Tests menu pagination logic for handling long lists of items.
- **`test_map_config_scanning.py`**: Tests map discovery (glob scanning) and registry pruning.
- **`test_menu_builder.py`**: Tests dynamic menu generation for the map registry.
- **`test_session_manager.py`**: Tests map-specific session persistence with path hashing.
- **`test_integration_map_loading.py`**: Integration tests for map loading and session restoration actions.

## Style Guidelines

All test files should follow the project's coding standards:

- **Style**: Formatted with `ruff format`.
- **Imports**: Use absolute imports from the `light_map` package (e.g., `from light_map.camera import Camera`).
- **Patterns**: Prefer `pytest` fixtures over `unittest.TestCase`.
