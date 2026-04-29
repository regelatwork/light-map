import base64
from io import BytesIO

import cv2
from PIL import Image


def generate_target(filename="calibration_target.svg"):
    # 100mm distance between centers
    # Markers: 20mm x 20mm

    # Use ArUco 4x4 Dict
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)

    # Generate Marker Images (200px for high res)
    # ID 0
    marker0_image = cv2.aruco.generateImageMarker(aruco_dict, 0, 200)
    # ID 1
    marker1_image = cv2.aruco.generateImageMarker(aruco_dict, 1, 200)

    # Convert to Base64 for embedding
    def img_to_b64(img):
        pil_img = Image.fromarray(img)
        buf = BytesIO()
        pil_img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    marker0_base64 = img_to_b64(marker0_image)
    marker1_base64 = img_to_b64(marker1_image)

    # SVG Units: 1 unit = 1 px. 96 DPI is standard.
    # 1 inch = 25.4 mm
    # 1 mm = 96 / 25.4 px ~= 3.7795 px

    mm_to_px = 96 / 25.4

    width_mm = 250
    height_mm = 120

    width_px = width_mm * mm_to_px
    height_px = height_mm * mm_to_px

    marker_size_mm = 40
    marker_size_px = marker_size_mm * mm_to_px

    distance_mm = 100
    distance_px = distance_mm * mm_to_px

    # Center logic
    center_x = width_px / 2
    center_y = height_px / 2

    # Marker 1 Center (ID 0)
    marker1_center_x = center_x - (distance_px / 2)
    marker1_x = marker1_center_x - (marker_size_px / 2)

    # Marker 2 Center (ID 1)
    marker2_center_x = center_x + (distance_px / 2)
    marker2_x = marker2_center_x - (marker_size_px / 2)

    marker_y = center_y - (marker_size_px / 2)

    svg_content = f"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg width="{width_mm}mm" height="{height_mm}mm" viewBox="0 0 {width_px} {height_px}" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
  <!-- Background for visibility -->
  <rect x="0" y="0" width="{width_px}" height="{height_px}" fill="white" />

  <!-- Marker 1 (ID 0) Left -->
  <image x="{marker1_x}" y="{marker_y}" width="{marker_size_px}" height="{marker_size_px}" xlink:href="data:image/png;base64,{marker0_base64}" />

  <!-- Marker 2 (ID 1) Right -->
  <image x="{marker2_x}" y="{marker_y}" width="{marker_size_px}" height="{marker_size_px}" xlink:href="data:image/png;base64,{marker1_base64}" />

  <!-- Text Label -->
  <text x="{center_x}" y="{center_y + marker_size_px + 20}" font-family="sans-serif" font-size="20" text-anchor="middle" fill="black">
    Calibration Target (ArUco 4x4 IDs 0 & 1) - Distance: {distance_mm}mm
  </text>

  <!-- Center Crosshairs for verification -->
  <line x1="{marker1_center_x}" y1="{marker_y}" x2="{marker1_center_x}" y2="{marker_y + marker_size_px}" stroke="red" stroke-width="1" />
  <line x1="{marker1_x}" y1="{center_y}" x2="{marker1_x + marker_size_px}" y2="{center_y}" stroke="red" stroke-width="1" />

  <line x1="{marker2_center_x}" y1="{marker_y}" x2="{marker2_center_x}" y2="{marker_y + marker_size_px}" stroke="red" stroke-width="1" />
  <line x1="{marker2_x}" y1="{center_y}" x2="{marker2_x + marker_size_px}" y2="{center_y}" stroke="red" stroke-width="1" />

</svg>
"""
    with open(filename, "w") as f:
        f.write(svg_content)
    print(f"Generated {filename}")


if __name__ == "__main__":
    generate_target()
