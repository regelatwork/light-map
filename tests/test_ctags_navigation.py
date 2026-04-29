import os
import subprocess

import pytest


@pytest.fixture(scope="module")
def tags_file():
    """Fixture to generate tags file and clean up after tests."""
    tags_path = os.path.join(os.getcwd(), "tags_test")

    # Use Universal Ctags to generate tags
    # We use -f to specify the output file so we don't overwrite any existing tags file
    command = [
        "ctags",
        "-R",
        "-f",
        tags_path,
        "--exclude=node_modules",
        "--exclude=.venv",
        "--exclude=.git",
        "--exclude=dist",
        "--exclude=build",
        "--langmap=TypeScript:+.tsx",
        ".",
    ]

    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        pytest.fail(f"ctags command failed: {e.stderr}")
    except FileNotFoundError:
        pytest.skip("ctags not installed")

    yield tags_path

    # Cleanup
    if os.path.exists(tags_path):
        os.remove(tags_path)


def test_tags_generation(tags_file):
    """Verify that a tags file was successfully generated."""
    assert os.path.exists(tags_file)
    assert os.path.getsize(tags_file) > 0


def test_find_python_symbol(tags_file):
    """Verify that a known Python symbol can be found in the tags file."""
    # We use grep -w to find the symbol exactly as suggested in the skill
    symbol = "InteractiveApp"
    try:
        result = subprocess.run(
            ["grep", "-w", symbol, tags_file],
            capture_output=True,
            text=True,
            check=True,
        )
        assert symbol in result.stdout
        # Verify it points to the correct file
        assert "src/light_map/interactive_app.py" in result.stdout
    except subprocess.CalledProcessError:
        pytest.fail(f"Could not find symbol '{symbol}' in {tags_file}")


def test_find_frontend_symbol(tags_file):
    """Verify that a known TypeScript/React symbol can be found in the tags file."""
    # Dashboards is a component in Dashboard.tsx
    symbol = "Dashboard"
    try:
        result = subprocess.run(
            ["grep", "-w", symbol, tags_file],
            capture_output=True,
            text=True,
            check=True,
        )
        assert symbol in result.stdout
        # Verify it points to the correct file
        assert "frontend/src/components/Dashboard.tsx" in result.stdout
    except subprocess.CalledProcessError:
        pytest.fail(
            f"Could not find symbol '{symbol}' in {tags_file}. Tags file content:\n{subprocess.run(['cat', tags_file], capture_output=True, text=True).stdout[:500]}..."
        )


if __name__ == "__main__":
    pytest.main([__file__])
