import os
import py_compile

import pytest


def test_main_compiles():
    """Verifies that src/light_map/__main__.py is syntactically correct and compiles."""
    file_path = "src/light_map/__main__.py"
    assert os.path.exists(file_path), f"{file_path} not found"

    # py_compile.compile returns the path to the byte-compiled file on success,
    # and raises a PyCompileError on failure.
    try:
        result = py_compile.compile(file_path, doraise=True)
        assert result is not None
    except py_compile.PyCompileError as e:
        pytest.fail(f"src/light_map/__main__.py failed to compile: {e}")


if __name__ == "__main__":
    # Allow running this test directly
    try:
        py_compile.compile("src/light_map/__main__.py", doraise=True)
        print("src/light_map/__main__.py compiled successfully.")
    except py_compile.PyCompileError as e:
        print(f"Compilation failed: {e}")
