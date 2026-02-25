import py_compile
import os
import pytest


def test_hand_tracker_compiles():
    """Verifies that hand_tracker.py is syntactically correct and compiles."""
    file_path = "hand_tracker.py"
    assert os.path.exists(file_path), f"{file_path} not found"

    # py_compile.compile returns the path to the byte-compiled file on success,
    # and raises a PyCompileError on failure.
    try:
        result = py_compile.compile(file_path, doraise=True)
        assert result is not None
    except py_compile.PyCompileError as e:
        pytest.fail(f"hand_tracker.py failed to compile: {e}")


if __name__ == "__main__":
    # Allow running this test directly
    try:
        py_compile.compile("hand_tracker.py", doraise=True)
        print("hand_tracker.py compiled successfully.")
    except py_compile.PyCompileError as e:
        print(f"Compilation failed: {e}")
