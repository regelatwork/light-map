import xml.etree.ElementTree as ET
import sys
from pathlib import Path

# Add scripts directory to path to import generate_calibration_target
scripts_dir = str(Path(__file__).resolve().parent.parent / "scripts")
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)

from generate_calibration_target import generate_target  # noqa: E402


def test_target_svg_contains_only_ruler_markers(tmp_path):
    output_file = tmp_path / "calibration_target.svg"
    generate_target(str(output_file))

    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")

    # Verify physical dimensions
    assert 'width="250mm"' in content
    assert 'height="120mm"' in content

    # Verify SVG structure and image tags
    tree = ET.fromstring(content)
    images = tree.findall(".//{http://www.w3.org/2000/svg}image")
    # Must contain exactly 2 marker images: ID 40 (left) and ID 41 (right)
    assert len(images) == 2

    # Verify ruler label text
    text_elements = tree.findall(".//{http://www.w3.org/2000/svg}text")
    assert len(text_elements) >= 1
    ruler_text = "".join(text_elements[0].itertext())
    assert "Light Map Physical PPI Calibration Ruler" in ruler_text
    assert "IDs 40 & 41" in ruler_text
    assert "100mm" in ruler_text

    # Verify that arena markers 42 through 49 are NOT mentioned or embedded
    for marker_id in range(42, 50):
        assert f"Arena Marker {marker_id}" not in content
        assert f"ID {marker_id}" not in content
