import os
import shutil
import tempfile
from pathlib import Path

# 1. Create a session-wide temporary directory for all tests
# This ensures that any StorageManager or configuration operations remain isolated.
_TEST_TEMP_DIR = tempfile.mkdtemp(prefix="light_map_test_")

# 2. Set XDG environment variables immediately upon importing this conftest
# This isolates any StorageManager calls that default to XDG directories,
# including module-level _DEFAULT_STORAGE initializations.
os.environ["XDG_CONFIG_HOME"] = str(Path(_TEST_TEMP_DIR) / "config")
os.environ["XDG_DATA_HOME"] = str(Path(_TEST_TEMP_DIR) / "data")
os.environ["XDG_STATE_HOME"] = str(Path(_TEST_TEMP_DIR) / "state")


def pytest_sessionfinish(session, exitstatus):
    """
    Hook to clean up the session-wide temporary directory.
    """
    shutil.rmtree(_TEST_TEMP_DIR, ignore_errors=True)
