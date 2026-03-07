# Feature: Robust Logging

## Problem Analysis

Currently, the project uses `print()` statements for debugging, error reporting, and informational messages. This approach has several limitations:

- **No Persistence**: Logs are lost once the console is cleared or the application is restarted.
- **Inconsistent Filtering**: There is no easy way to toggle between different levels of verbosity (e.g., DEBUG vs. INFO vs. ERROR).
- **Difficult Post-Mortem**: Without a persistent log file, diagnosing crashes that occur "in the wild" is challenging.
- **Hardware Integration**: Errors from GStreamer, MediaPipe, or OpenCV are often swallowed or only visible if the console is monitored in real-time.

## Goals

1. **Standardize Logging**: Replace `print()` statements with a structured `logging` module.
1. **Persistent Storage**: Save logs to a file (e.g., `light_map.log`) with rotation to prevent disk exhaustion.
1. **Configurable Verbosity**: Allow users to set the logging level via CLI arguments.
1. **Crash Reporting**: Ensure unhandled exceptions are logged before the application exits.
1. **Real-time Monitoring**: Maintain console output for immediate feedback during development.

## Proposed Design

### 1. Centralized Initialization

A new utility function `setup_logging` is located in `src/light_map/display_utils.py`. It provides a unified entry point for all Light Map applications (`python -m light_map`, `scripts/calibrate.py`, `scripts/projector_calibration.py`).

```python
import logging
import sys
from logging.handlers import RotatingFileHandler

def setup_logging(level=logging.INFO, log_file=None):
    """Configures the root logger with console and file handlers."""
    if log_file is None:
        log_file = _DEFAULT_STORAGE.get_state_path("light_map.log")

    # Format: 2026-02-23 02:23:03,009 - INFO - [python -m light_map:123] - Message
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Console Handler (Stderr for cleaner pipe usage)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File Handler (Consolidated light_map.log with rotation)
    try:
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file, maxBytes=10*1024*1024, backupCount=5
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        print(f"Warning: Failed to initialize file logging: {e}")
```

### 2. Consolidated Attribution

To ensure clear debugging across multiple scripts, all entry points use **named loggers** (`logging.getLogger(__name__)`) and the formatter explicitly includes the **filename and line number**. This prevents all entries from appearing as "root" and allows developers to quickly trace logs back to their source.

### 3. Application Integration

- **`python -m light_map`**: Uses `--log-level` and `--log-file` arguments.
- **`scripts/calibrate.py` & `scripts/projector_calibration.py`**: Automatically initialize logging to the shared `light_map.log` at the start of `main()`.

### 3. Systematic Replacement of `print()`

All existing `print()` calls in `src/light_map/` will be replaced with appropriate `logging` calls:

- **Errors/Exceptions**: `logging.error("Message: %s", e, exc_info=True)`
- **Warnings**: `logging.warning("Resource mismatch: ...")`
- **General Events**: `logging.info("Map loaded: %s", map_path)`
- **Detailed Debugging**: `logging.debug("Gesture detected: %s", gesture_type)`

### 4. Crash Handling

Update the `try...except` block in `python -m light_map` to use `logging.critical` for unhandled exceptions.

```python
try:
    # ... main application loop ...
except Exception as e:
    logging.critical("Unhandled exception in main loop", exc_info=True)
finally:
    # ... cleanup ...
```

## Implementation Phases

### Phase 1: Infrastructure (Inquiry light_map-40s.3)

- Create `setup_logging` utility.
- Add CLI arguments to `python -m light_map`.
- Initialize logging at startup.

### Phase 2: Core Systems Migration (Inquiry light_map-40s.5.2)

- Update `InteractiveApp`, `Camera`, `Renderer`, and `MapSystem` to use logging.

### Phase 3: Vision & Scene Migration (Inquiry light_map-40s.5.2)

- Update `TrackingCoordinator`, `InputProcessor`, and all `Scene` subclasses.

## Verification Plan

### Automated Tests

- **`tests/test_logging.py`**:
  - Verify `setup_logging` creates the log file.
  - Verify log rotation works.
  - Verify different levels are captured correctly by a `ListHandler` or similar.

### Manual Verification

- Run with `--log-level DEBUG` and verify console output.
- Induce a fake error (e.g., missing map file) and verify it appears in `light_map.log` with a stack trace.
