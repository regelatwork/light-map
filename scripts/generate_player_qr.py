#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys
import qrcode
import qrcode.image.svg
import re

def main():
    parser = argparse.ArgumentParser(description="Generate a US-Letter sized QR code for the Player Tactical Dashboard.")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host address of the Light Map server")
    parser.add_argument("--port", type=int, default=8000, help="Port of the Light Map server")
    parser.add_argument("--output", type=str, default="player_qr.svg", help="Output file path (default: player_qr.svg)")
    parser.add_argument("--pdf", action="store_true", help="Also export as PDF using Inkscape")
    
    args = parser.parse_args()
    
    url = f"http://{args.host}:{args.port}/player"
    print(f"Generating QR code for: {url}")
    
    # Generate QR code using the qrcode library
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=1, # 1 unit per module
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    # Create SVG image (using Path factory)
    factory = qrcode.image.svg.SvgPathImage
    img = qr.make_image(image_factory=factory)
    
    # Extract the path from the generated image
    svg_str = img.to_string().decode()
    match = re.search(r'd="([^"]+)"', svg_str)
    if not match:
        print("Error: Could not extract path from QR code")
        sys.exit(1)
        
    qr_path = match.group(1)
    
    # Calculate scale to make it fit nicely
    # Standard QR v1 with border is 29x29 modules.
    # We want it to be about 400px wide on our 816px canvas.
    # 400 / 29 = 13.8 approx
    
    us_letter_svg = f"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg
   width="8.5in"
   height="11in"
   viewBox="0 0 816 1056"
   version="1.1"
   xmlns="http://www.w3.org/2000/svg">
  <rect width="100%" height="100%" fill="white" />
  
  <text x="408" y="150" font-family="sans-serif" font-size="32" font-weight="bold" text-anchor="middle" fill="#22d3ee">
    Light Map Tactical Dashboard
  </text>
  
  <g transform="translate(208, 250) scale(13.8)">
    <path d="{qr_path}" fill="black" stroke="none" />
  </g>
  
  <text x="408" y="750" font-family="monospace" font-size="20" text-anchor="middle" fill="#475569">
    {url}
  </text>
  
  <text x="408" y="800" font-family="sans-serif" font-size="16" text-anchor="middle" fill="#94a3b8">
    Scan to join the session as a player.
  </text>
</svg>
"""
    
    with open(args.output, "w") as f:
        f.write(us_letter_svg)
        
    print(f"Successfully generated: {args.output}")
    
    if args.pdf:
        pdf_path = args.output.replace(".svg", ".pdf")
        print(f"Exporting to PDF using Inkscape...")
        try:
            subprocess.run(["inkscape", args.output, "--export-filename=" + pdf_path], check=True, capture_output=True)
            print(f"Successfully generated: {pdf_path}")
        except subprocess.CalledProcessError as e:
            print("Error exporting PDF via Inkscape:")
            print(e.stderr.decode())
        except FileNotFoundError:
            print("Error: Inkscape not found. PDF export skipped.")

if __name__ == "__main__":
    main()
