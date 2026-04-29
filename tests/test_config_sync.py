import os

import pytest

from scripts.generate_ts_schema import OUTPUT_FILE


def test_ts_schema_is_synchronized():
    """
    Verifies that the generated TypeScript schema file is up-to-date with the Pydantic models.
    If this test fails, run 'python3 scripts/generate_ts_schema.py' to update.
    """
    if not os.path.exists(OUTPUT_FILE):
        pytest.fail(
            f"Generated TS schema file not found at {OUTPUT_FILE}. Run scripts/generate_ts_schema.py first."
        )

    # Read current content on disk
    with open(OUTPUT_FILE) as f:
        on_disk_content = f.read()

    # Generate in-memory content (we'll capture it by temporarily mocking the open/write if necessary,
    # but since generate_ts_schema.py is simple, we can just run its logic and compare)

    # Simple approach: Run the generator and check git diff or just re-read and compare.
    # More robust for a test: Mock the output file path in the generator.
    import scripts.generate_ts_schema as generator

    # Save original path
    original_output = generator.OUTPUT_FILE
    temp_output = OUTPUT_FILE + ".tmp"
    generator.OUTPUT_FILE = temp_output

    try:
        generator.main()

        with open(temp_output) as f:
            generated_content = f.read()

        if on_disk_content != generated_content:
            pytest.fail(
                "\nERROR: Configuration schema is out of sync.\n"
                "The Pydantic models in src/light_map/core/config_schema.py have changed.\n"
                f"Please run 'python3 scripts/generate_ts_schema.py' to update {OUTPUT_FILE}."
            )
    finally:
        generator.OUTPUT_FILE = original_output
        if os.path.exists(temp_output):
            os.remove(temp_output)


def test_config_validation():
    """Verifies that GlobalConfigSchema correctly validates and typecasts."""
    from light_map.core.config_schema import GlobalConfigSchema

    # Valid payload
    payload = {"pointer_offset_mm": "75.5", "enable_hand_masking": "true"}
    validated = GlobalConfigSchema(**payload)
    assert validated.pointer_offset_mm == 75.5
    assert validated.enable_hand_masking is True

    # Invalid payload (out of range)
    with pytest.raises(ValueError):
        GlobalConfigSchema(pointer_offset_mm=1000.0)  # Max is 500

    # Invalid type
    with pytest.raises(ValueError):
        GlobalConfigSchema(pointer_offset_mm="not a number")


def test_recursive_sync_to_dataclass():
    """Verifies that nested Pydantic models correctly sync to nested dataclasses."""
    from light_map.core.config_schema import MapEntrySchema, ViewportStateSchema
    from light_map.core.config_utils import sync_pydantic_to_dataclass
    from light_map.map.map_config import MapEntry

    # Initial state
    entry = MapEntry()
    assert entry.viewport.zoom == 1.0
    assert entry.scale_factor == 1.0

    # Partial update: just nested viewport zoom
    update = MapEntrySchema(viewport=ViewportStateSchema(zoom=2.5))
    sync_pydantic_to_dataclass(update, entry)

    # Check propagation
    assert entry.viewport.zoom == 2.5
    # Other fields should remain defaults
    assert entry.viewport.x == 0.0
    assert entry.scale_factor == 1.0


def test_aruco_defaults_int_keys():
    """Verifies that ArUco IDs (int keys) are correctly handled between JSON (strings) and Pydantic (ints)."""
    from light_map.core.config_schema import TokenConfigSchema

    # 1. Loading from JSON-like payload (string keys)
    payload = {"aruco_defaults": {"42": {"name": "Test Token", "type": "PC"}}}
    config = TokenConfigSchema(**payload)

    # Pydantic should have cast key to int
    assert 42 in config.aruco_defaults
    assert isinstance(list(config.aruco_defaults.keys())[0], int)
    assert config.aruco_defaults[42].name == "Test Token"

    # 2. Dumping to JSON (string keys)
    # mode='json' converts types to JSON-compatible ones
    json_data = config.model_dump(mode="json")
    assert "42" in json_data["aruco_defaults"]
    assert isinstance(list(json_data["aruco_defaults"].keys())[0], str)
