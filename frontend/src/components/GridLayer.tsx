import React from 'react';
import { useSystemState } from '../hooks/useSystemState';

export const GridLayer: React.FC = () => {
  const { grid_spacing_svg, grid_origin_svg_x, grid_origin_svg_y, isConnected } = useSystemState();

  if (!isConnected || grid_spacing_svg <= 0) {
    return null;
  }

  const lines: React.ReactNode[] = [];
  const numLines = 50; // Render 50 lines in each direction
  const half = Math.floor(numLines / 2);

  // Vertical lines
  for (let i = -half; i <= half; i++) {
    const x = grid_origin_svg_x + i * grid_spacing_svg;
    lines.push(
      <line
        key={`v-${i}`}
        x1={x}
        y1={grid_origin_svg_y - half * grid_spacing_svg}
        x2={x}
        y2={grid_origin_svg_y + half * grid_spacing_svg}
        stroke="#e5e7eb"
        strokeWidth="1"
      />
    );
  }

  // Horizontal lines
  for (let i = -half; i <= half; i++) {
    const y = grid_origin_svg_y + i * grid_spacing_svg;
    lines.push(
      <line
        key={`h-${i}`}
        x1={grid_origin_svg_x - half * grid_spacing_svg}
        y1={y}
        x2={grid_origin_svg_x + half * grid_spacing_svg}
        y2={y}
        stroke="#e5e7eb"
        strokeWidth="1"
      />
    );
  }

  // Origin marker
  lines.push(
    <circle
      key="origin"
      cx={grid_origin_svg_x}
      cy={grid_origin_svg_y}
      r={grid_spacing_svg / 4}
      fill="rgba(59, 130, 246, 0.2)"
      stroke="#3b82f6"
      strokeWidth="2"
    />
  );

  return <g>{lines}</g>;
};
