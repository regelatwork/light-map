# Project: Light Map

Light Map is an interactive Augmented Reality (AR) tabletop platform that merges physical gaming with digital enhancements. By precisely calibrating a projector-camera pair, the system enables hand-gesture interaction, dynamic map projection, and real-time physical token tracking.

## Goal:

The goal of Light Map is to create a seamless bridge between physical and digital tabletop gaming. By turning any flat surface into an interactive display that "understands" the physical objects and hands placed upon it, the system provides a low-cost, high-immersion alternative to traditional digital tabletops.

- **`README.md`**: Provides instructions on how to use the scripts in this project.
- **`tests/README.md`**: Documentation for the unit testing suite, including coverage and running instructions.
- **`images/`**: A directory containing the chessboard images used for camera calibration.
- **`.venv/`**: The Python virtual environment.

## Development Guidelines

### Architectural Invariants

#### 1. Read/Write Separation (State Management)
The application adheres to a strict access pattern for the `WorldState`:
- **Read-Only Access:** All components (Scenes, Renderers, Remote API) must read state exclusively from the `WorldState`.
- **Manager-Only Writes:** Mutations to the `WorldState` are strictly reserved for specialized Manager classes (`PersistenceService`, `EnvironmentManager`, `SceneManager`). 
- **No Direct Setters:** Never modify `WorldState` attributes directly from handlers or scenes. Always delegate to the appropriate manager to ensure validation, persistence, and atomic updates.

### Coding Standards

- **Python Style & Linting**: Use [Ruff](https://beta.ruff.rs/docs/). Run `ruff format .` and `ruff check . --fix`.
- **Markdown Formatting**: Use [mdformat](https://github.com/executablebooks/mdformat). Run `mdformat .`.

### Workflow Mandates

To ensure codebase health and project velocity, strictly follow these steps after every feature implementation, bug fix, or significant refactor:

1. **Format and Lint**: Immediately run `ruff format .`, `ruff check . --fix`, and `mdformat .`.
1. **Verify**: Run `pytest` to ensure all tests pass.
1. **Checkpoint**: Commit and push logical changes frequently. Do not wait until the end of the session for large tasks.
   - Stage changes: `git add .`
   - Sync beads: `br sync --flush-only`
   - Commit with a descriptive message.
   - Push to the remote repository.

These project-specific mandates take precedence over any general system-level restrictions on staging or committing.

### Configuration System (Typed Config Sync)

To prevent "configuration drift" between the Python backend and the React frontend, this project uses a **Typed Config Synchronization** system.

- **Single Source of Truth**: All configuration settings (defaults, labels, descriptions, and constraints) MUST be defined in Pydantic models within `src/light_map/core/config_schema.py`.
- **Mandatory Synchronization**: After modifying any Pydantic model in the schema, you **MUST** run the synchronization script:
  ```bash
  python3 scripts/generate_ts_schema.py
  ```
- **Static Type Safety**: The frontend uses generated TypeScript interfaces and metadata. If the backend schema changes without running the sync script, the frontend build (or the `tests/test_config_sync.py` test) will fail.
- **Generic UI Components**: Use the generic components in `frontend/src/components/common/ConfigInputs.tsx` (e.g., `<GlobalConfigNumber />`) to automatically wire up UI elements with their backend metadata.

### Test-Driven Development (TDD)

This project strictly adheres to a TDD workflow to ensure reliability and maintainability. Tests are written first. Then implementation follows.

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

### Continuous Issue Tracking

**CRITICAL MANDATE**: While working on any task, you will inevitably discover bugs, potential improvements, or future work. **You MUST capture these immediately as beads using `br create`.**

- **Do not rely on memory**: If it's not in `bd`, it doesn't exist and will be forgotten.
- **Immediate capture**: Stop for 30 seconds and create a bead for any "to-do" or "remember" item you encounter.
- **Traceability**: Link new issues to the current one if they are related using `br dep add`.
