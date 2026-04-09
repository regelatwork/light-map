import os
import re
from light_map.core.common_types import (
    GestureType,
    ResultType,
    SceneId,
    SelectionType,
    MenuActions,
    GmPosition,
)
from light_map.visibility.visibility_types import VisibilityType


def parse_ts_enums(file_path):
    with open(file_path, "r") as f:
        content = f.read()

    # Find all export enum Blocks
    # export enum Name {
    #   KEY = 'value',
    # }
    enum_pattern = re.compile(r"export enum (\w+) \{([^}]+)\}", re.MULTILINE)
    matches = enum_pattern.findall(content)

    enums = {}
    for name, body in matches:
        # Parse KEY = 'value'
        values = {}
        # Support both 'value' and "value"
        value_pattern = re.compile(r"(\w+)\s*=\s*['\"]([^'\"]+)['\"]")
        for k, v in value_pattern.findall(body):
            values[k] = v
        enums[name] = values
    return enums


def test_enums_sync():
    """
    Ensures that Python enums and TypeScript enums are in sync.
    This prevents bugs where backend sends a value that the frontend doesn't recognize.
    """
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ts_file = os.path.join(root_dir, "frontend", "src", "types", "system.ts")

    assert os.path.exists(ts_file), f"Frontend types file not found at {ts_file}"

    ts_enums = parse_ts_enums(ts_file)

    # List of enums to check (Frontend Name, Python Enum Class)
    checks = [
        ("VisibilityType", VisibilityType),
        ("ResultType", ResultType),
        ("GestureType", GestureType),
        ("SceneId", SceneId),
        ("SelectionType", SelectionType),
        ("MenuActions", MenuActions),
        ("GmPosition", GmPosition),
    ]

    for ts_name, py_enum in checks:
        assert ts_name in ts_enums, f"Enum {ts_name} missing from frontend types"

        ts_values = ts_enums[ts_name]
        py_values = {e.name: e.value for e in py_enum}

        # Check that all Python values exist in TypeScript and match
        for name, value in py_values.items():
            assert name in ts_values, (
                f"Enum member {name} missing from frontend {ts_name}. Please add it to system.ts"
            )
            assert ts_values[name] == value, (
                f"Enum member {name} value mismatch in {ts_name}: TS={ts_values[name]}, PY={value}"
            )

        # Check that TypeScript doesn't have extra values (strict sync)
        for name in ts_values:
            assert name in py_values, (
                f"Frontend enum {ts_name} has extra member {name} not in Python. Remove it or add to backend."
            )
