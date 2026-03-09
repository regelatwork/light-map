import React, { useState, useEffect, useCallback } from 'react';
import { useSystemState } from '../hooks/useSystemState';
import { useCanvas } from './CanvasContext';
import { saveGridConfig } from '../services/api';

export const GridLayer: React.FC = () => {
  const { grid_spacing_svg, grid_origin_svg_x, grid_origin_svg_y, isConnected } = useSystemState();
  const { screenToWorld } = useCanvas();

  // Local state for dragging
  const [isDragging, setIsDragging] = useState(false);
  const [dragOrigin, setDragOrigin] = useState({ x: 0, y: 0 });

  const displayedOrigin = isDragging
    ? dragOrigin
    : { x: grid_origin_svg_x, y: grid_origin_svg_y };

  const handleMouseDown = (e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent panning the canvas
    setIsDragging(true);
    setDragOrigin({ x: grid_origin_svg_x, y: grid_origin_svg_y });
  };

  const handleMouseMove = useCallback(
    (e: MouseEvent) => {
      if (!isDragging) return;

      const worldPos = screenToWorld(e.clientX, e.clientY);
      if (worldPos) {
        setDragOrigin(worldPos);
      }
    },
    [isDragging, screenToWorld]
  );

  const handleMouseUp = useCallback(async () => {
    if (!isDragging) return;
    setIsDragging(false);

    try {
      await saveGridConfig(dragOrigin.x, dragOrigin.y);
    } catch (err) {
      console.error('Failed to save grid config:', err);
    }
  }, [isDragging, dragOrigin.x, dragOrigin.y]);

  // Add global mouse listeners during drag
  useEffect(() => {
    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    }
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, handleMouseMove, handleMouseUp]);

  if (!isConnected || grid_spacing_svg <= 0) {
    return null;
  }

  const lines: React.ReactNode[] = [];
  const numLines = 50;
  const half = Math.floor(numLines / 2);

  // Vertical lines
  for (let i = -half; i <= half; i++) {
    const x = displayedOrigin.x + i * grid_spacing_svg;
    lines.push(
      <line
        key={`v-${i}`}
        x1={x}
        y1={displayedOrigin.y - half * grid_spacing_svg}
        x2={x}
        y2={displayedOrigin.y + half * grid_spacing_svg}
        stroke="#e5e7eb"
        strokeWidth="1"
      />
    );
  }

  // Horizontal lines
  for (let i = -half; i <= half; i++) {
    const y = displayedOrigin.y + i * grid_spacing_svg;
    lines.push(
      <line
        key={`h-${i}`}
        x1={displayedOrigin.x - half * grid_spacing_svg}
        y1={y}
        x2={displayedOrigin.x + half * grid_spacing_svg}
        y2={y}
        stroke="#e5e7eb"
        strokeWidth="1"
      />
    );
  }

  return (
    <g>
      {lines}
      {/* Draggable Origin handle */}
      <circle
        cx={displayedOrigin.x}
        cy={displayedOrigin.y}
        r={grid_spacing_svg / 3}
        fill={isDragging ? 'rgba(59, 130, 246, 0.5)' : 'rgba(59, 130, 246, 0.2)'}
        stroke="#3b82f6"
        strokeWidth="2"
        className="cursor-pointer"
        onMouseDown={handleMouseDown}
      />
      <text
        x={displayedOrigin.x + grid_spacing_svg / 2}
        y={displayedOrigin.y - 10}
        className="fill-blue-500 text-[10px] font-mono select-none pointer-events-none"
      >
        {Math.round(displayedOrigin.x)}, {Math.round(displayedOrigin.y)}
      </text>
    </g>
  );
};
