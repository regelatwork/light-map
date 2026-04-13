import React, { useState, useEffect, useCallback } from 'react';
import { useSystemState } from '../hooks/useSystemState';
import { useCanvas } from './CanvasContext';
import { useCalibration, CalibrationMode } from './CalibrationContext';
import { saveGridConfig } from '../services/api';
import { GridType } from '../types/system';

type InteractionMode = 'IDLE' | 'MOVING_ORIGIN' | 'SCALING';

const SCALE_DISTANCES = [2, 5, 10, 20, 50];

export const GridLayer: React.FC = () => {
  const { world, grid_spacing_svg, grid_origin_svg_x, grid_origin_svg_y, isConnected } =
    useSystemState();
  const { screenToWorld } = useCanvas();
  const { activeMode } = useCalibration();
  const isGridEditMode = activeMode === CalibrationMode.GRID;
  const groupRef = React.useRef<SVGGElement>(null);

  const rotation = world.viewport?.rotation || 0;
  // Determine if handles are swapped visually on screen
  const isRotated90 = Math.abs(rotation % 180) === 90;

  useEffect(() => {
    if (world.scene && world.scene !== 'LOADING' && isGridEditMode) {
      console.log(
        'GridLayer Debug - Scene:',
        world.scene,
        'Spacing:',
        grid_spacing_svg,
        'Origin:',
        grid_origin_svg_x,
        grid_origin_svg_y
      );
    }
  }, [world.scene, grid_spacing_svg, grid_origin_svg_x, grid_origin_svg_y, isGridEditMode]);

  const isCalibrating =
    isGridEditMode ||
    (typeof world.scene === 'string' &&
      (world.scene.toUpperCase().includes('CALIBRATE_MAP_GRID') ||
        world.scene.includes('MapGridCalibrationScene')));

  // Use a default spacing if not calibrated yet, but ONLY if we are in the calibration scene
  const effectiveSpacing = grid_spacing_svg > 0 ? grid_spacing_svg : isCalibrating ? 50 : 0;
  const effectiveOriginX = grid_spacing_svg > 0 ? grid_origin_svg_x : isCalibrating ? 0 : 0;
  const effectiveOriginY = grid_spacing_svg > 0 ? grid_origin_svg_y : isCalibrating ? 0 : 0;
  const gridType = world.grid_type || GridType.SQUARE;

  // Local state for dragging
  const [interactionMode, setInteractionMode] = useState<InteractionMode>('IDLE');
  const [dragOrigin, setDragOrigin] = useState({ x: 0, y: 0 });
  const [dragSpacing, setDragSpacing] = useState(0);
  const [dragScaleDistance, setDragScaleDistance] = useState(1);

  const displayedOrigin =
    interactionMode !== 'IDLE' ? dragOrigin : { x: effectiveOriginX, y: effectiveOriginY };
  const displayedSpacing = interactionMode === 'SCALING' ? dragSpacing : effectiveSpacing;

  const handleMouseDownOrigin = (e: React.MouseEvent) => {
    if (!isGridEditMode) return;
    e.stopPropagation();
    setInteractionMode('MOVING_ORIGIN');
    setDragOrigin({ x: effectiveOriginX, y: effectiveOriginY });
    setDragSpacing(effectiveSpacing);
  };

  const handleMouseDownScale = (e: React.MouseEvent, distUnits: number) => {
    if (!isGridEditMode) return;
    e.stopPropagation();
    setInteractionMode('SCALING');
    setDragOrigin({ x: effectiveOriginX, y: effectiveOriginY });
    setDragSpacing(effectiveSpacing);
    setDragScaleDistance(distUnits);
  };

  const handleMouseMove = useCallback(
    (e: MouseEvent) => {
      if (interactionMode === 'IDLE') return;

      const worldPos = screenToWorld(e.clientX, e.clientY, groupRef.current || undefined);
      if (!worldPos) return;

      if (interactionMode === 'MOVING_ORIGIN') {
        setDragOrigin(worldPos);
      } else if (interactionMode === 'SCALING') {
        const dx = worldPos.x - dragOrigin.x;
        const dy = worldPos.y - dragOrigin.y;
        const currentDist = Math.sqrt(dx * dx + dy * dy);

        if (currentDist > 5) {
          // The handle grabbed was at distUnits grid cells away
          // Current distance should equal spacing * distUnits
          const newSpacing = currentDist / dragScaleDistance;
          setDragSpacing(newSpacing);
        }
      }
    },
    [interactionMode, dragOrigin, screenToWorld, dragScaleDistance]
  );

  const handleMouseUp = useCallback(async () => {
    if (interactionMode === 'IDLE') return;

    const finalMode = interactionMode;
    const finalOrigin = dragOrigin;
    const finalSpacing = dragSpacing;

    setInteractionMode('IDLE');

    try {
      await saveGridConfig(
        finalOrigin.x,
        finalOrigin.y,
        finalMode === 'SCALING' ? finalSpacing : effectiveSpacing
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

  const gridElements: React.ReactNode[] = [];

  if (gridType === GridType.SQUARE) {
    const numLines = 100; // Increased for better coverage on large maps
    const half = Math.floor(numLines / 2);

    // Vertical lines
    for (let i = -half; i <= half; i++) {
      const x = displayedOrigin.x + i * displayedSpacing;
      gridElements.push(
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
      gridElements.push(
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
  } else {
    // Hex Grid - Optimized with a single path
    const hexSize = displayedSpacing / Math.sqrt(3);
    const isPointy = gridType === GridType.HEX_POINTY;
    
    // Draw 3 segments per hex to create a mesh without duplicates
    // Standard axial coordinate system
    const numHex = 25;
    const pathSegments: string[] = [];

    for (let q = -numHex; q <= numHex; q++) {
      for (let r = -numHex; r <= numHex; r++) {
        let cx, cy;
        if (isPointy) {
          cx = hexSize * Math.sqrt(3) * (q + r/2);
          cy = hexSize * 1.5 * r;
        } else {
          cx = hexSize * 1.5 * q;
          cy = hexSize * Math.sqrt(3) * (r + q/2);
        }

        const wx = displayedOrigin.x + cx;
        const wy = displayedOrigin.y + cy;

        // Draw segments (first 3 segments of each hex to avoid overlaps)
        for (let i = 0; i < 3; i++) {
          const angle1 = (60 * i + (isPointy ? 30 : 0)) * Math.PI / 180;
          const angle2 = (60 * (i + 1) + (isPointy ? 30 : 0)) * Math.PI / 180;
          const x1 = wx + hexSize * Math.cos(angle1);
          const y1 = wy + hexSize * Math.sin(angle1);
          const x2 = wx + hexSize * Math.cos(angle2);
          const y2 = wy + hexSize * Math.sin(angle2);
          pathSegments.push(`M ${x1} ${y1} L ${x2} ${y2}`);
        }
      }
    }
    gridElements.push(
      <path
        key="hex-mesh"
        d={pathSegments.join(' ')}
        stroke="#3b82f6"
        strokeOpacity={0.3}
        strokeWidth="1"
        fill="none"
      />
    );
  }

  return (
    <g ref={groupRef}>
      {gridElements}

      {/* Handles only visible in edit mode */}
      {isGridEditMode && (
        <>
          {/* Origin handle (Green) */}
          <circle
            cx={displayedOrigin.x}
            cy={displayedOrigin.y}
            r={Math.max(12, displayedSpacing / 4)}
            fill={
              interactionMode === 'MOVING_ORIGIN'
                ? 'rgba(34, 197, 94, 0.6)'
                : 'rgba(34, 197, 94, 0.3)'
            }
            stroke="#22c55e"
            strokeWidth="2"
            className="cursor-move"
            onMouseDown={handleMouseDownOrigin}
          />

          {/* Scale handles Horizontal */}
          {SCALE_DISTANCES.map((dist) => (
            <circle
              key={`scale-h-${dist}`}
              cx={displayedOrigin.x + dist * displayedSpacing}
              cy={displayedOrigin.y}
              r={Math.max(6, displayedSpacing / 6)}
              fill={
                interactionMode === 'SCALING' && dragScaleDistance === dist
                  ? 'rgba(59, 130, 246, 0.8)'
                  : 'rgba(59, 130, 246, 0.3)'
              }
              stroke="#3b82f6"
              strokeWidth="2"
              className={isRotated90 ? "cursor-ns-resize" : "cursor-ew-resize"}
              onMouseDown={(e) => handleMouseDownScale(e, dist)}
            />
          ))}

          {/* Scale handles Vertical */}
          {SCALE_DISTANCES.map((dist) => (
            <circle
              key={`scale-v-${dist}`}
              cx={displayedOrigin.x}
              cy={displayedOrigin.y + dist * displayedSpacing}
              r={Math.max(6, displayedSpacing / 6)}
              fill={
                interactionMode === 'SCALING' && dragScaleDistance === dist
                  ? 'rgba(59, 130, 246, 0.8)'
                  : 'rgba(59, 130, 246, 0.3)'
              }
              stroke="#3b82f6"
              strokeWidth="2"
              className={isRotated90 ? "cursor-ew-resize" : "cursor-ns-resize"}
              onMouseDown={(e) => handleMouseDownScale(e, dist)}
            />
          ))}

          <text
            x={displayedOrigin.x}
            y={displayedOrigin.y - 15}
            textAnchor="middle"
            className="fill-green-600 text-[14px] font-bold font-mono select-none pointer-events-none drop-shadow-sm"
          >
            Origin: {Math.round(displayedOrigin.x)}, {Math.round(displayedOrigin.y)}
          </text>

          {interactionMode === 'SCALING' && (
            <text
              x={displayedOrigin.x + dragScaleDistance * displayedSpacing}
              y={displayedOrigin.y + 25}
              textAnchor="middle"
              className="fill-blue-600 text-[14px] font-bold font-mono select-none pointer-events-none drop-shadow-sm"
            >
              Spacing: {displayedSpacing.toFixed(1)}
            </text>
          )}
        </>
      )}
    </g>
  );
};
