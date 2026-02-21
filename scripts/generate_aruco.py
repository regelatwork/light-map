import cv2
import base64
from PIL import Image
from io import BytesIO
import argparse

def img_to_b64(img):
    pil_img = Image.fromarray(img)
    buf = BytesIO()
    pil_img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")

def generate_aruco_svg(filename, mode, marker_size_in=1.0):
    # ArUco dictionary to use
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)

    # Conversion factor from inches to pixels (96 DPI standard)
    inch_to_px = 96.0
    margin_inches = 0.5

    if mode == "sizes":
        sizes_inches = [2.0, 1.5, 1.0, 0.75, 0.5, 0.25]
        total_height_inches = sum(sizes_inches) + (len(sizes_inches) + 1) * margin_inches
        max_width_inches = max(sizes_inches) + 2 * margin_inches
        width_px = max_width_inches * inch_to_px
        height_px = total_height_inches * inch_to_px

        svg_content = f"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg width="{max_width_inches}in" height="{total_height_inches}in" viewBox="0 0 {width_px} {height_px}" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
  <rect x="0" y="0" width="{width_px}" height="{height_px}" fill="white" />
"""
        current_y_px = margin_inches * inch_to_px
        center_x_px = width_px / 2

        for i, size_in in enumerate(sizes_inches):
            size_px = size_in * inch_to_px
            marker_img = cv2.aruco.generateImageMarker(aruco_dict, i, 200)
            marker_b64 = img_to_b64(marker_img)
            x_px = center_x_px - (size_px / 2)
            y_px = current_y_px
            svg_content += f"""
  <image x="{x_px}" y="{y_px}" width="{size_px}" height="{size_px}" xlink:href="data:image/png;base64,{marker_b64}" />
  <text x="{center_x_px}" y="{y_px + size_px + 15}" font-family="sans-serif" font-size="12" text-anchor="middle" fill="black">
    ID: {i}, Size: {size_in:.2f}"
  </text>
"""
            current_y_px += size_px + margin_inches * inch_to_px

    elif mode == "grid":
        rows, cols = 5, 4
        marker_size_px = marker_size_in * inch_to_px
        margin_px = margin_inches * inch_to_px

        width_px = cols * marker_size_px + (cols + 1) * margin_px
        height_px = rows * marker_size_px + (rows + 1) * margin_px
        
        width_in = width_px / inch_to_px
        height_in = height_px / inch_to_px

        svg_content = f"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg width="{width_in}in" height="{height_in}in" viewBox="0 0 {width_px} {height_px}" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
  <rect x="0" y="0" width="{width_px}" height="{height_px}" fill="white" />
"""
        for r in range(rows):
            for c in range(cols):
                i = r * cols + c
                marker_img = cv2.aruco.generateImageMarker(aruco_dict, i, 200)
                marker_b64 = img_to_b64(marker_img)
                
                x_px = margin_px + c * (marker_size_px + margin_px)
                y_px = margin_px + r * (marker_size_px + margin_px)
                
                svg_content += f"""
  <image x="{x_px}" y="{y_px}" width="{marker_size_px}" height="{marker_size_px}" xlink:href="data:image/png;base64,{marker_b64}" />
  <text x="{x_px + marker_size_px/2}" y="{y_px + marker_size_px + 15}" font-family="sans-serif" font-size="10" text-anchor="middle" fill="black">
    ID: {i}
  </text>
"""

    svg_content += "\n</svg>"
    with open(filename, "w") as f:
        f.write(svg_content)
    print(f"Generated {filename} in {mode} mode (size: {marker_size_in:.2f}in / {marker_size_in*25.4:.1f}mm)")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate ArUco markers in SVG format")
    parser.add_argument("--mode", choices=["sizes", "grid"], default="sizes", help="Generation mode")
    parser.add_argument("--size", type=float, help="Marker size in inches (for grid mode)")
    parser.add_argument("--size-mm", type=float, help="Marker size in millimeters (for grid mode)")
    parser.add_argument("--output", default="aruco_markers.svg", help="Output filename")
    
    args = parser.parse_args()
    
    size_in = args.size
    if args.size_mm is not None:
        size_in = args.size_mm / 25.4
    elif size_in is None:
        size_in = 1.0 # Default to 1 inch if neither is specified
        
    generate_aruco_svg(args.output, args.mode, size_in)
