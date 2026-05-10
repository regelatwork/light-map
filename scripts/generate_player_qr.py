#!/usr/bin/env python3
import argparse
import os
import subprocess
import sys
import tempfile

def main():
    parser = argparse.ArgumentParser(description="Generate a US-Letter sized QR code for the Player Tactical Dashboard.")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host address of the Light Map server")
    parser.add_argument("--port", type=int, default=8000, help="Port of the Light Map server")
    parser.add_argument("--output", type=str, default="player_qr.svg", help="Output file path (default: player_qr.svg)")
    parser.add_argument("--pdf", action="store_true", help="Also export as PDF using Inkscape")
    
    args = parser.parse_args()
    
    url = f"http://{args.host}:{args.port}/player"
    print(f"Generating QR code for: {url}")
    
    # Path to inkscape extension script
    inkscape_ext_path = "/usr/share/inkscape/extensions/render_barcode_qrcode.py"
    if not os.path.exists(inkscape_ext_path):
        print(f"Error: Inkscape QR extension not found at {inkscape_ext_path}")
        sys.exit(1)
        
    # Use the venv python to run the extension script (since we installed dependencies there)
    venv_python = os.path.join(os.path.dirname(__file__), "..", ".venv", "bin", "python3")
    if not os.path.exists(venv_python):
        # Fallback to current python
        venv_python = sys.executable

    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tmp_empty:
        tmp_empty.write(b'<svg xmlns="http://www.w3.org/2000/svg"/>')
        tmp_empty_path = tmp_empty.name

    try:
        # Generate the QR code SVG using the extension script
        # We capture stdout as it prints the SVG there
        cmd = [
            venv_python, 
            inkscape_ext_path, 
            "--text", url,
            "--modulesize", "4",
            tmp_empty_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print("Error generating QR code:")
            print(result.stderr)
            sys.exit(1)
            
        qr_svg_content = result.stdout
        
        # Extract the path/group from the generated SVG
        # The extension outputs a full SVG, we want to embed its contents
        import re
        # Find the first <g> or <path> that isn't the outer <svg>
        # Simplified: just take everything between <svg ...> and </svg>
        match = re.search(r'<svg[^>]*>(.*)</svg>', qr_svg_content, re.DOTALL)
        if not match:
            print("Error: Could not parse generated QR code SVG")
            sys.exit(1)
            
        qr_elements = match.group(1)
        
        # US Letter template (8.5 x 11 inches)
        # 96 DPI: 816 x 1056 px
        # QR code centered, URL text below
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
  
  <g transform="translate(208, 250) scale(3.5)">
    {qr_elements}
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
            print(f"Exporting to PDF: {pdf_path}...")
            subprocess.run(["inkscape", args.output, "--export-filename=" + pdf_path], check=True)
            print(f"Successfully generated: {pdf_path}")
            
    finally:
        if os.path.exists(tmp_empty_path):
            os.remove(tmp_empty_path)

if __name__ == "__main__":
    main()
