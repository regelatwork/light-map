import sys

def generate_target(filename="calibration_target.svg"):
    # 100mm distance between centers
    # Markers: 20mm x 20mm squares
    
    # SVG Units: 1 unit = 1 px. 96 DPI is standard.
    # 1 inch = 25.4 mm
    # 1 mm = 96 / 25.4 px ~= 3.7795 px
    
    mm_to_px = 96 / 25.4
    
    width_mm = 200
    height_mm = 100
    
    width_px = width_mm * mm_to_px
    height_px = height_mm * mm_to_px
    
    marker_size_mm = 20
    marker_size_px = marker_size_mm * mm_to_px
    
    distance_mm = 100
    distance_px = distance_mm * mm_to_px
    
    # Center logic
    cx = width_px / 2
    cy = height_px / 2
    
    # Marker 1 Center
    m1_cx = cx - (distance_px / 2)
    m1_x = m1_cx - (marker_size_px / 2)
    
    # Marker 2 Center
    m2_cx = cx + (distance_px / 2)
    m2_x = m2_cx - (marker_size_px / 2)
    
    m_y = cy - (marker_size_px / 2)
    
    svg_content = f"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg width="{width_mm}mm" height="{height_mm}mm" viewBox="0 0 {width_px} {height_px}" xmlns="http://www.w3.org/2000/svg">
  <!-- Background for visibility -->
  <rect x="0" y="0" width="{width_px}" height="{height_px}" fill="white" />
  
  <!-- Marker 1 (Left) -->
  <rect x="{m1_x}" y="{m_y}" width="{marker_size_px}" height="{marker_size_px}" fill="black" />
  
  <!-- Marker 2 (Right) -->
  <rect x="{m2_x}" y="{m_y}" width="{marker_size_px}" height="{marker_size_px}" fill="black" />
  
  <!-- Text Label -->
  <text x="{cx}" y="{cy + marker_size_px}" font-family="sans-serif" font-size="20" text-anchor="middle" fill="black">
    Distance betweeen centers: {distance_mm}mm
  </text>
  
  <!-- Center Crosshairs for verification -->
  <line x1="{m1_cx}" y1="{m_y}" x2="{m1_cx}" y2="{m_y + marker_size_px}" stroke="white" stroke-width="1" />
  <line x1="{m1_x}" y1="{cy}" x2="{m1_x + marker_size_px}" y2="{cy}" stroke="white" stroke-width="1" />
  
  <line x1="{m2_cx}" y1="{m_y}" x2="{m2_cx}" y2="{m_y + marker_size_px}" stroke="white" stroke-width="1" />
  <line x1="{m2_x}" y1="{cy}" x2="{m2_x + marker_size_px}" y2="{cy}" stroke="white" stroke-width="1" />

</svg>
"""
    with open(filename, "w") as f:
        f.write(svg_content)
    print(f"Generated {filename}")

if __name__ == "__main__":
    generate_target()
