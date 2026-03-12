import React, { useState, useEffect, useCallback } from 'react';
import { useSystemState } from '../hooks/useSystemState';
import { useCanvas } from './CanvasContext';
import { saveGridConfig } from '../services/api';

type InteractionMode = 'IDLE' | 'MOVING_ORIGIN' | 'SCALING';

export const GridLayer: React.FC = () => {
  const { world, grid_spacing_svg, grid_origin_svg_x, grid_origin_svg_y, isConnected } = useSystemState();
  const { screenToWorld } = useCanvas();

  useEffect(() => {
    if (world.scene && world.scene !== 'LOADING') {
      console.log('GridLayer Debug - Scene:', world.scene, 'Spacing:', grid_spacing_svg, 'Origin:', grid_origin_svg_x, grid_origin_svg_y);
    }
  }, [world.scene, grid_spacing_svg, grid_origin_svg_x, grid_origin_svg_y]);

  const isCalibrating = typeof world.scene === 'string' && 
    (world.scene.toUpperCase().includes('CALIBRATE_MAP_GRID') || 
     world.scene.includes('MapGridCalibrationScene') ||
     world.scene === 'VIEWING'); // Temporary for debugging


  // Use a default spacing if not calibrated yet, but ONLY if we are in the calibration scene
  const effectiveSpacing = grid_spacing_svg > 0 ? grid_spacing_svg : isCalibrating ? 50 : 0;
  const effectiveOriginX = grid_spacing_svg > 0 ? grid_origin_svg_x : isCalibrating ? 0 : 0;
  const effectiveOriginY = grid_spacing_svg > 0 ? grid_origin_svg_y : isCalibrating ? 0 : 0;

  // Local state for dragging
  const [interactionMode, setInteractionMode] = useState<InteractionMode>('IDLE');
  const [dragOrigin, setDragOrigin] = useState({ x: 0, y: 0 });
  const [dragSpacing, setDragSpacing] = useState(0);

  const displayedOrigin =
    interactionMode !== 'IDLE' ? dragOrigin : { x: effectiveOriginX, y: effectiveOriginY };
  const displayedSpacing = interactionMode === 'SCALING' ? dragSpacing : effectiveSpacing;

  const handleMouseDownOrigin = (e: React.MouseEvent) => {
    e.stopPropagation();
    setInteractionMode('MOVING_ORIGIN');
    setDragOrigin({ x: effectiveOriginX, y: effectiveOriginY });
    setDragSpacing(effectiveSpacing);
  };

  const handleMouseDownScale = (e: React.MouseEvent) => {
    e.stopPropagation();
    setInteractionMode('SCALING');
    setDragOrigin({ x: effectiveOriginX, y: effectiveOriginY });
    setDragSpacing(effectiveSpacing);
  };

  const handleMouseMove = useCallback(
    (e: MouseEvent) => {
      if (interactionMode === 'IDLE') return;

      const worldPos = screenToWorld(e.clientX, e.clientY);
      if (!worldPos) return;

      if (interactionMode === 'MOVING_ORIGIN') {
        setDragOrigin(worldPos);
      } else if (interactionMode === 'SCALING') {
        // Calculate new spacing based on distance from origin to current mouse
        // We assume the handle is 1 unit away originally (or we can just calculate distance)
        // Let's say the handle we grabbed was at (origin.x + spacing, origin.y)
        const dx = worldPos.x - dragOrigin.x;
        const dy = worldPos.y - dragOrigin.y;
        const dist = Math.sqrt(dx * dx + dy * dy);

        // If we want "drag any cross", we'd need to know which one.
        // For simplicity, let's just use the distance to the mouse as the new spacing
        // if the user grabbed a handle that's exactly 1 unit away.
        if (dist > 5) {
          // Minimum spacing threshold
          setDragSpacing(dist);
        }
      }
    },
    [interactionMode, dragOrigin, screenToWorld]
  );

  const handleMouseUp = useCallback(async () => {
    if (interactionMode === 'IDLE') return;

    const finalMode = interactionMode;
    setInteractionMode('IDLE');

    try {
      await saveGridConfig(
        dragOrigin.x,
        dragOrigin.y,
        finalMode === 'SCALING' ? dragSpacing : effectiveSpacing
      );
    } catch (err) {
      console.error('Failed to save grid config:', err);
    }
  }, [interactionMode, dragOrigin, dragSpacing, effectiveSpacing]);

  // Add global mouse listeners during drag
  useEffect(() => {
    if (interactionMode !== 'IDLE') {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    }
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [interactionMode, handleMouseMove, handleMouseUp]);

  if (!isConnected || effectiveSpacing <= 0) {
    return null;
  }

  const lines: React.ReactNode[] = [];
  const numLines = 40;
  const half = Math.floor(numLines / 2);

  // Vertical lines
  for (let i = -half; i <= half; i++) {
    const x = displayedOrigin.x + i * displayedSpacing;
    lines.push(
      <line
        key={`v-${i}`}
        x1={x}
        y1={displayedOrigin.y - half * displayedSpacing}
        x2={x}
        y2={displayedOrigin.y + half * displayedSpacing}
        stroke="#3b82f6"
        strokeOpacity={0.3}
        strokeWidth="1"
      />
    );
  }

  // Horizontal lines
  for (let i = -half; i <= half; i++) {
    const y = displayedOrigin.y + i * displayedSpacing;
    lines.push(
      <line
        key={`h-${i}`}
        x1={displayedOrigin.x - half * displayedSpacing}
        y1={y}
        x2={displayedOrigin.x + half * displayedSpacing}
        y2={y}
        stroke="#3b82f6"
        strokeOpacity={0.3}
        strokeWidth="1"
      />
    );
  }

  return (
    <g>
      {lines}

      {/* Origin handle (Green) */}
      <circle
        cx={displayedOrigin.x}
        cy={displayedOrigin.y}
        r={Math.max(8, displayedSpacing / 4)}
        fill={
          interactionMode === 'MOVING_ORIGIN' ? 'rgba(34, 197, 94, 0.6)' : 'rgba(34, 197, 94, 0.3)'
        }
        stroke="#22c55e"
        strokeWidth="2"
        className="cursor-move"
        onMouseDown={handleMouseDownOrigin}
      />

      {/* Scale handle (Blue, 1 unit to the right) */}
      <circle
        cx={displayedOrigin.x + displayedSpacing}
        cy={displayedOrigin.y}
        r={Math.max(6, displayedSpacing / 6)}
        fill={interactionMode === 'SCALING' ? 'rgba(59, 130, 246, 0.6)' : 'rgba(59, 130, 246, 0.3)'}
        stroke="#3b82f6"
        strokeWidth="2"
        className="cursor-ew-resize"
        onMouseDown={handleMouseDownScale}
      />

      <text
        x={displayedOrigin.x}
        y={displayedOrigin.y - 15}
        textAnchor="middle"
        className="fill-green-600 text-[12px] font-bold font-mono select-none pointer-events-none drop-shadow-sm"
      >
        Origin: {Math.round(displayedOrigin.x)}, {Math.round(displayedOrigin.y)}
      </text>

      {interactionMode === 'SCALING' && (
        <text
          x={displayedOrigin.x + displayedSpacing}
          y={displayedOrigin.y + 25}
          textAnchor="middle"
          className="fill-blue-600 text-[12px] font-bold font-mono select-none pointer-events-none drop-shadow-sm"
        >
          Spacing: {displayedSpacing.toFixed(1)}
        </text>
      )}
    </g>
  );
};
