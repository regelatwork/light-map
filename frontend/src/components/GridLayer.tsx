import React, { useState, useEffect } from 'react';
import { useSystemState } from '../hooks/useSystemState';
import { useCanvas } from './CanvasContext';
import { saveGridConfig } from '../services/api';

export const GridLayer: React.FC = () => {
  const { grid_spacing_svg, grid_origin_svg_x, grid_origin_svg_y, isConnected } = useSystemState();
  const { screenToWorld } = useCanvas();

  // Local state for dragging
  const [isDragging, setIsDragging] = useState(false);
  const [localOrigin, setLocalOrigin] = useState({ x: 0, y: 0 });

  // Sync local state when world state changes (if not dragging)
  useEffect(() => {
    if (!isDragging) {
      setLocalOrigin({ x: grid_origin_svg_x, y: grid_origin_svg_y });
    }
  }, [grid_origin_svg_x, grid_origin_svg_y, isDragging]);

  if (!isConnected || grid_spacing_svg <= 0) {
    return null;
  }

  const handleMouseDown = (e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent panning the canvas
    setIsDragging(true);
  };

  const handleMouseMove = (e: MouseEvent) => {
    if (!isDragging) return;

    const worldPos = screenToWorld(e.clientX, e.clientY);
    if (worldPos) {
      setLocalOrigin(worldPos);
    }
  };

  const handleMouseUp = async () => {
    if (!isDragging) return;
    setIsDragging(false);

    try {
      await saveGridConfig(localOrigin.x, localOrigin.y);
    } catch (err) {
      console.error('Failed to save grid config:', err);
      // Revert to world state
      setLocalOrigin({ x: grid_origin_svg_x, y: grid_origin_svg_y });
    }
  };

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
  }, [isDragging, localOrigin]);

  const lines: React.ReactNode[] = [];
  const numLines = 50;
  const half = Math.floor(numLines / 2);

  // Vertical lines
  for (let i = -half; i <= half; i++) {
    const x = localOrigin.x + i * grid_spacing_svg;
    lines.push(
      <line
        key={`v-${i}`}
        x1={x}
        y1={localOrigin.y - half * grid_spacing_svg}
        x2={x}
        y2={localOrigin.y + half * grid_spacing_svg}
        stroke="#e5e7eb"
        strokeWidth="1"
      />
    );
  }

  // Horizontal lines
  for (let i = -half; i <= half; i++) {
    const y = localOrigin.y + i * grid_spacing_svg;
    lines.push(
      <line
        key={`h-${i}`}
        x1={localOrigin.x - half * grid_spacing_svg}
        y1={y}
        x2={localOrigin.x + half * grid_spacing_svg}
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
        cx={localOrigin.x}
        cy={localOrigin.y}
        r={grid_spacing_svg / 3}
        fill={isDragging ? 'rgba(59, 130, 246, 0.5)' : 'rgba(59, 130, 246, 0.2)'}
        stroke="#3b82f6"
        strokeWidth="2"
        className="cursor-pointer"
        onMouseDown={handleMouseDown}
      />
      <text
        x={localOrigin.x + grid_spacing_svg / 2}
        y={localOrigin.y - 10}
        className="fill-blue-500 text-[10px] font-mono select-none pointer-events-none"
      >
        {Math.round(localOrigin.x)}, {Math.round(localOrigin.y)}
      </text>
    </g>
  );
};
