# Project: Light Map

Light Map is an interactive Augmented Reality (AR) tabletop platform that merges physical gaming with digital enhancements. By precisely calibrating a projector-camera pair, the system enables hand-gesture interaction, dynamic map projection, and real-time physical token tracking.

## Goal:

The goal of Light Map is to create a seamless bridge between physical and digital tabletop gaming. By turning any flat surface into an interactive display that "understands" the physical objects and hands placed upon it, the system provides a low-cost, high-immersion alternative to traditional digital tabletops.

- **`README.md`**: Provides instructions on how to use the scripts in this project.
- **`tests/README.md`**: Documentation for the unit testing suite, including coverage and running instructions.
- **`images/`**: A directory containing the chessboard images used for camera calibration.
- **`.venv/`**: The Python virtual environment.

## Development Guidelines

### Coding Standards

- **Python Style & Linting**: Use [Ruff](https://beta.ruff.rs/docs/). Run `ruff format .` and `ruff check . --fix`.
- **Markdown Formatting**: Use [mdformat](https://github.com/executablebooks/mdformat). Run `mdformat .`.

### Test-Driven Development (TDD)

This project strictly adheres to a TDD workflow to ensure reliability and maintainability.

- **TDD Lifecycle**:
  1. **Red**: Write a failing test for a new feature or bug fix.
  1. **Green**: Implement the minimum code necessary to pass the test.
  1. **Refactor**: Clean up the implementation while ensuring all tests still pass.
- **Execution**: Run tests using `pytest`.
- **Mandate**: All new features and bug fixes MUST be accompanied by corresponding tests.
- **Coverage**:
  - Run coverage reporting with `pytest --cov=src`.
  - Aim for a minimum coverage threshold of **80%**.
- **Structure**:
  - All tests reside in the `tests/` directory.
  - Test files MUST be prefixed with `test_` (e.g., `tests/test_camera.py`).
- **Best Practices**:
  - Use mocks and stubs (via `unittest.mock` or `pytest-mock`) for hardware-dependent components like the camera, projector, and GStreamer pipelines to ensure tests are fast and deterministic.
  - Leverage `pytest` fixtures for common setup/teardown logic.

