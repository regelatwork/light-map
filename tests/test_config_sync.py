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
    with open(OUTPUT_FILE, "r") as f:
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

        with open(temp_output, "r") as f:
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
