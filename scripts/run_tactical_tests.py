#!/usr/bin/env python3
import os
import sys
import yaml
import json
import numpy as np
import cv2
import subprocess

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from light_map.core.common_types import Token, GridType, AppConfig
from light_map.state.world_state import WorldState
from light_map.map.map_system import MapSystem
from light_map.visibility.visibility_engine import VisibilityEngine, _numba_trace_path
from light_map.rendering.svg.loader import SVGLoader
from light_map.rendering.layers.tactical_overlay_layer import TacticalOverlayLayer

STATUS_MAP = {
    0: "CLEAR",
    1: "BLOCKED",
    2: "OBSCURED_LOW"
}

def run_test_case(case_path: str):
    case_name = os.path.splitext(os.path.basename(case_path))[0]
    yaml_path = case_path
    svg_path = case_path.replace(".yaml", ".svg")
    
    if not os.path.exists(svg_path):
        print(f"Error: {svg_path} not found.")
        return False

    with open(yaml_path, 'r') as f:
        config = yaml.safe_all_load(f) if hasattr(yaml, 'safe_all_load') else yaml.safe_load(f)
        if isinstance(config, list):
            config = config[0]  # Handle cases where yaml.safe_load returns a list

    # 1. Initialize Loader and determine scaling
    loader = SVGLoader(svg_path)
    
    grid_config = config.get("grid", {})
    grid_type_str = grid_config.get("type", "SQUARE")
    grid_type = GridType[grid_type_str]
    num_cells = grid_config.get("cells", 20)
    
    # Scaling for 20 cells on largest dimension
    svg_w, svg_h = loader.width, loader.height
    if grid_type == GridType.SQUARE:
        spacing_svg = max(svg_w, svg_h) / num_cells
    else:
        # For HEX, assume orientation defines the 20-cell axis
        # (Simplified for now, treating like SQUARE if orientation unknown)
        spacing_svg = max(svg_w, svg_h) / num_cells
    
    # 2. Setup Engine and Mask
    engine = VisibilityEngine(grid_spacing_svg=spacing_svg)
    # Mask is 16px per unit (unit = spacing_svg)
    # So svg_to_mask_scale = 16 / spacing_svg
    mask_w = int(svg_w * engine.svg_to_mask_scale)
    mask_h = int(svg_h * engine.svg_to_mask_scale)
    engine.blocker_mask = np.zeros((mask_h, mask_w), dtype=np.uint8)
    
    # Rasterize SVG geometry
    blockers = loader.get_visibility_blockers()
    for b in blockers:
        # Scale points to mask space
        pts = (np.array(b.points) * engine.svg_to_mask_scale).astype(np.int32)
        val = 0
        from light_map.visibility.visibility_types import VisibilityType
        if b.type == VisibilityType.WALL:
            val = 255
        elif b.type == VisibilityType.DOOR:
            val = 200  # Assume closed
        elif b.type == VisibilityType.LOW_OBJECT:
            val = 50
        elif b.type == VisibilityType.TALL_OBJECT:
            val = 100
        
        if val > 0:
            if len(pts) > 2:
                cv2.fillPoly(engine.blocker_mask, [pts], val)
            else:
                cv2.polylines(engine.blocker_mask, [pts], False, val, thickness=2)

    # 3. Setup Tokens
    a_cfg = config.get("attacker", {})
    t_cfg = config.get("target", {})
    
    # Grid -> World (SVG)
    # center = (grid_coord + 0.5) * spacing
    ax = (a_cfg.get("grid_x", 0) + 0.5) * spacing_svg
    ay = (a_cfg.get("grid_y", 0) + 0.5) * spacing_svg
    tx = (t_cfg.get("grid_x", 0) + 0.5) * spacing_svg
    ty = (t_cfg.get("grid_y", 0) + 0.5) * spacing_svg
    
    tokens = []
    for i, t_data in enumerate(config.get("tokens", [])):
        tx_val = (t_data.get("grid_x", 0) + 0.5) * spacing_svg
        ty_val = (t_data.get("grid_y", 0) + 0.5) * spacing_svg
        t_obj = Token(id=100+i, world_x=tx_val, world_y=ty_val, size=t_data.get("size", 1))
        tokens.append(t_obj)
        engine.stamp_token_footprint(engine.blocker_mask, t_obj)

    attacker = Token(id=1, world_x=ax, world_y=ay, size=a_cfg.get("size", 1))
    target = Token(id=2, world_x=tx, world_y=ty, size=t_cfg.get("size", 1))

    # 4. Run Calculation
    res = engine.calculate_token_cover_bonuses(attacker, target)
    
    # 5. Generate JSON Output
    output_json = {
        "case_name": case_name,
        "grid_params": {
            "spacing_svg": float(spacing_svg),
            "svg_to_mask_scale": float(engine.svg_to_mask_scale),
            "mask_resolution": [mask_w, mask_h]
        },
        "cover_result": {
            "ac_bonus": res.ac_bonus,
            "reflex_bonus": res.reflex_bonus,
            "total_ratio": float(res.total_ratio),
            "wall_ratio": float(res.wall_ratio),
            "best_apex_svg": [float(res.best_apex[0] / engine.svg_to_mask_scale), float(res.best_apex[1] / engine.svg_to_mask_scale)],
            "wedges": [
                {
                    "status": STATUS_MAP.get(seg.status, str(seg.status)),
                    "start_idx": seg.start_idx,
                    "end_idx": seg.end_idx
                } for seg in res.segments
            ],
            "boundary_samples": [
                {
                    "mask_xy": p.tolist(),
                    "angle_rad": float(np.arctan2(p[1] - res.best_apex[1], p[0] - res.best_apex[0])),
                    # Recalculate status for the report (same logic as engine)
                    "status": STATUS_MAP.get(_numba_trace_path(int(p[0]), int(p[1]), int(res.best_apex[0]), int(res.best_apex[1]), engine.blocker_mask), "UNKNOWN")
                } for p in res.npc_pixels
            ]
        }
    }
    
    res_dir = "tests/tactical_cases/results"
    json_path = os.path.join(res_dir, f"{case_name}.json")
    with open(json_path, 'w') as f:
        json.dump(output_json, f, indent=2)

    # 6. Generate PNG (128px per cell)
    # Target PNG resolution
    px_per_cell = 128
    png_w = int(num_cells * px_per_cell)
    png_h = int((svg_h / svg_w) * png_w) if svg_w > svg_h else int(num_cells * px_per_cell)
    if svg_h > svg_w:
        png_h = int(num_cells * px_per_cell)
        png_w = int((svg_w / svg_h) * png_h)
        
    # Render base map using Inkscape
    # We'll use a temporary file for the base map
    base_map_path = os.path.join(res_dir, f"{case_name}_base.png")
    try:
        subprocess.run([
            "inkscape", 
            "-o", base_map_path, 
            "-w", str(png_w),
            "-h", str(png_h),
            svg_path
        ], check=True, capture_output=True)
        base_img = cv2.imread(base_map_path)
    except Exception as e:
        print(f"Warning: Inkscape rendering failed ({e}), using black background.")
        base_img = np.zeros((png_h, png_w, 3), dtype=np.uint8)
    finally:
        if os.path.exists(base_map_path):
            os.remove(base_map_path)

    # Setup Mock App for TacticalOverlayLayer
    state = WorldState()
    state.inspected_token_id = attacker.id
    # We need a dummy mask for the layer to render
    state.inspected_token_mask = np.full((10, 10), 255, dtype=np.uint8)
    state.tokens = [attacker, target] + tokens
    state.tactical_bonuses = {target.id: res}
    
    # MapSystem mock
    map_system = MapSystem(AppConfig(width=png_w, height=png_h, projector_matrix=np.eye(3)))
    # Scale from SVG to Screen
    # png_w / svg_w = scale
    map_scale = png_w / svg_w
    map_system.state.zoom = map_scale
    map_system.state.x = 0
    map_system.state.y = 0
    
    layer = TacticalOverlayLayer(state, map_system, engine)
    patches, _ = layer.render(0.0)
    
    # Composite result
    final_img = base_img.copy()
    for p in patches:
        # BGRA to BGR with alpha blending
        if p.data.shape[2] == 4:
            overlay = p.data[:, :, :3]
            alpha = p.data[:, :, 3] / 255.0
            alpha = alpha[:, :, np.newaxis]
            
            y1, y2 = p.y, p.y + p.height
            x1, x2 = p.x, p.x + p.width
            # Ensure coordinates are within bounds
            y1, y2 = max(0, y1), min(png_h, y2)
            x1, x2 = max(0, x1), min(png_w, x2)
            
            # Slice patch to match bounds if needed
            oh, ow = y2 - y1, x2 - x1
            if oh <= 0 or ow <= 0:
                continue
            
            ov_slice = overlay[:oh, :ow]
            al_slice = alpha[:oh, :ow]
            
            final_img[y1:y2, x1:x2] = (ov_slice * al_slice + final_img[y1:y2, x1:x2] * (1.0 - al_slice)).astype(np.uint8)

    # Draw tokens as actual footprints and border points
    for t in [attacker, target] + tokens:
        # Get border points in mask space
        # We re-run the footprint logic locally to get points for rendering
        cx_mask = int(t.world_x * engine.svg_to_mask_scale)
        cy_mask = int(t.world_y * engine.svg_to_mask_scale)
        size = t.size if t.size is not None else 1
        footprint, _ = engine._calculate_token_footprint_with_planes(
            cx_mask, cy_mask, size, GridType.SQUARE, ignore_blockers=True
        )
        border_points = engine._get_footprint_border_points(footprint)
        
        # Scale mask points to screen pixels
        # mask -> world (SVG) = 1/svg_to_mask_scale
        # world -> screen = map_scale
        scale = map_scale / engine.svg_to_mask_scale
        
        # Draw footprint (faint fill)
        mask_indices = np.where(footprint > 0)
        for my, mx in zip(mask_indices[0], mask_indices[1]):
            px, py = int(mx * scale), int(my * scale)
            if t.id == attacker.id:
                color = (0, 40, 0)
            elif t.id == target.id:
                color = (0, 0, 40)
            else:
                color = (40, 40, 0)
            cv2.rectangle(final_img, (px, py), (px+int(scale), py+int(scale)), color, -1)

        # Draw border points
        for p in border_points:
            px, py = int(p[0] * scale), int(p[1] * scale)
            if t.id == attacker.id:
                color = (0, 255, 0)
            elif t.id == target.id:
                color = (0, 0, 255)
            else:
                color = (255, 255, 0)
            cv2.circle(final_img, (px, py), 2, color, -1)

        # Draw label
        sx, sy = map_system.world_to_screen(t.world_x, t.world_y)
        cv2.putText(final_img, f"{t.id}", (int(sx)-10, int(sy)+10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    # Draw raycasting lines from Best Apex to target boundary
    apex_scale = map_scale / engine.svg_to_mask_scale
    ax_px, ay_px = int(res.best_apex[0] * apex_scale), int(res.best_apex[1] * apex_scale)
    
    for p in res.npc_pixels:
        tx_px, ty_px = int(p[0] * apex_scale), int(p[1] * apex_scale)
        # Recalculate status for color
        status = _numba_trace_path(int(p[0]), int(p[1]), int(res.best_apex[0]), int(res.best_apex[1]), engine.blocker_mask)
        if status == 0: # CLEAR
            color = (0, 255, 0, 100) # Green
        elif status == 2: # OBSCURED
            color = (0, 255, 255, 100) # Yellow
        else: # BLOCKED
            color = (0, 0, 255, 100) # Red
        
        cv2.line(final_img, (ax_px, ay_px), (tx_px, ty_px), color[:3], 1)

    png_path = os.path.join(res_dir, f"{case_name}.png")
    cv2.imwrite(png_path, final_img)
    
    # Comparison
    golden_path = os.path.join("tests/tactical_cases/golden", f"{case_name}.json")
    if not os.path.exists(golden_path):
        print(f"MISSING GOLDEN: {case_name}. Run bless script to create.")
        return False
    
    with open(golden_path, 'r') as f:
        golden_json = json.load(f)
    
    if output_json == golden_json:
        print(f"PASS: {case_name}")
        return True
    else:
        print(f"FAIL: {case_name} (JSON mismatch)")
        # Simple diff print could be added here
        return False

def main():
    cases_dir = "tests/tactical_cases"
    if not os.path.exists(cases_dir):
        print(f"Directory {cases_dir} not found.")
        return

    failed = []
    for f in os.listdir(cases_dir):
        if f.endswith(".yaml"):
            success = run_test_case(os.path.join(cases_dir, f))
            if not success:
                failed.append(f)
    
    if failed:
        print(f"\nFailed cases: {', '.join(failed)}")
        print("\nTo bless all cases, run:")
        print("  .venv/bin/python3 scripts/bless_tactical_tests.py")
        print("\nTo bless specific cases, run:")
        for f in failed:
            name = os.path.splitext(f)[0]
            print(f"  .venv/bin/python3 scripts/bless_tactical_tests.py {name}")
        sys.exit(1)
    else:
        print("\nAll tactical tests passed.")

if __name__ == "__main__":
    main()
