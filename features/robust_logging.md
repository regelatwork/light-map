# Feature: Robust Logging

## Problem Analysis

Currently, the project uses `print()` statements for debugging, error reporting, and informational messages. This approach has several limitations:
- **No Persistence**: Logs are lost once the console is cleared or the application is restarted.
- **Inconsistent Filtering**: There is no easy way to toggle between different levels of verbosity (e.g., DEBUG vs. INFO vs. ERROR).
- **Difficult Post-Mortem**: Without a persistent log file, diagnosing crashes that occur "in the wild" is challenging.
- **Hardware Integration**: Errors from GStreamer, MediaPipe, or OpenCV are often swallowed or only visible if the console is monitored in real-time.

## Goals

1. **Standardize Logging**: Replace `print()` statements with a structured `logging` module.
2. **Persistent Storage**: Save logs to a file (e.g., `light_map.log`) with rotation to prevent disk exhaustion.
3. **Configurable Verbosity**: Allow users to set the logging level via CLI arguments.
4. **Crash Reporting**: Ensure unhandled exceptions are logged before the application exits.
5. **Real-time Monitoring**: Maintain console output for immediate feedback during development.

## Proposed Design

### 1. Centralized Initialization

A new utility function `setup_logging` will be added to `src/light_map/display_utils.py` or a new `src/light_map/utils.py`.

```python
import logging
import sys
from logging.handlers import RotatingFileHandler

def setup_logging(level=logging.INFO, log_file="light_map.log"):
    """Configures the root logger with console and file handlers."""
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File Handler (with rotation)
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10*1024*1024, backupCount=5
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    logging.info("Logging initialized at level %s", logging.getLevelName(level))
```

### 2. Integration with `AppConfig` and `hand_tracker.py`

- **`AppConfig`**: Add `log_level` and `log_file` fields.
- **`hand_tracker.py`**: Add `--log-level` (DEBUG, INFO, WARNING, ERROR) and `--log-file` arguments. Call `setup_logging` at the start of `main()`.

### 3. Systematic Replacement of `print()`

All existing `print()` calls in `src/light_map/` will be replaced with appropriate `logging` calls:
- **Errors/Exceptions**: `logging.error("Message: %s", e, exc_info=True)`
- **Warnings**: `logging.warning("Resource mismatch: ...")`
- **General Events**: `logging.info("Map loaded: %s", map_path)`
- **Detailed Debugging**: `logging.debug("Gesture detected: %s", gesture_type)`

### 4. Crash Handling

Update the `try...except` block in `hand_tracker.py` to use `logging.critical` for unhandled exceptions.

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
- Add CLI arguments to `hand_tracker.py`.
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
