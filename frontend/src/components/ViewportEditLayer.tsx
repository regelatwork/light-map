import React, { useState, useEffect, useCallback } from 'react';
import { useSystemState } from '../hooks/useSystemState';
import { useCanvas } from './CanvasContext';
import { useCalibration, CalibrationMode } from './CalibrationContext';
import { setViewportConfig } from '../services/api';

type InteractionMode = 'IDLE' | 'PANNING' | 'ZOOMING_TOP' | 'ZOOMING_BOTTOM' | 'ZOOMING_LEFT' | 'ZOOMING_RIGHT';

export const ViewportEditLayer: React.FC = () => {
  const { world, config, grid_spacing_svg, isConnected } = useSystemState();
  const { screenToWorld } = useCanvas();
  const { activeMode } = useCalibration();
  const groupRef = React.useRef<SVGGElement>(null);

  const isVisible = activeMode === CalibrationMode.VIEWPORT;

  // Local state for dragging
  const [interactionMode, setInteractionMode] = useState<InteractionMode>('IDLE');
  const [dragState, setDragState] = useState({
    x: 0,
    y: 0,
    zoom: 1.0,
  });

  const currentVp = world.viewport || { x: 0, y: 0, zoom: 1.0, rotation: 0 };
  
  const displayedVp = interactionMode !== 'IDLE' ? dragState : currentVp;

  const projW = config.proj_res?.[0] || 1920;
  const projH = config.proj_res?.[1] || 1080;

  // Viewport dimensions in world space
  const vW = projW / displayedVp.zoom;
  const vH = projH / displayedVp.zoom;

  // Rectangle bounds
  const xMin = displayedVp.x - vW / 2;
  const yMin = displayedVp.y - vH / 2;

  const handleMouseDownCenter = (e: React.MouseEvent) => {
    e.stopPropagation();
    setInteractionMode('PANNING');
    setDragState({ x: currentVp.x, y: currentVp.y, zoom: currentVp.zoom });
  };

  const handleMouseDownSide = (e: React.MouseEvent, mode: InteractionMode) => {
    e.stopPropagation();
    setInteractionMode(mode);
    setDragState({ x: currentVp.x, y: currentVp.y, zoom: currentVp.zoom });
  };

  const handleMouseMove = useCallback(
    (e: MouseEvent) => {
      if (interactionMode === 'IDLE') return;

      const worldPos = screenToWorld(e.clientX, e.clientY, groupRef.current || undefined);
      if (!worldPos) return;

      if (interactionMode === 'PANNING') {
        // Snap to grid if available
        const spacing = grid_spacing_svg || 1;
        const snappedX = Math.round(worldPos.x / spacing) * spacing;
        const snappedY = Math.round(worldPos.y / spacing) * spacing;
        setDragState((prev) => ({ ...prev, x: snappedX, y: snappedY }));
      } else {
        // Zooming logic - Opposite Side Fixed
        // Fixed Point (P_fixed) is the midpoint of the opposite edge
        let pFixed = { x: currentVp.x, y: currentVp.y };
        const currentVW = projW / currentVp.zoom;
        const currentVH = projH / currentVp.zoom;

        if (interactionMode === 'ZOOMING_TOP') {
          pFixed = { x: currentVp.x, y: currentVp.y + currentVH / 2 };
          const newH = Math.max(10, Math.abs(worldPos.y - pFixed.y));
          const newZoom = projH / newH;
          setDragState({
            zoom: newZoom,
            y: pFixed.y - newH / 2,
            x: currentVp.x,
          });
        } else if (interactionMode === 'ZOOMING_BOTTOM') {
          pFixed = { x: currentVp.x, y: currentVp.y - currentVH / 2 };
          const newH = Math.max(10, Math.abs(worldPos.y - pFixed.y));
          const newZoom = projH / newH;
          setDragState({
            zoom: newZoom,
            y: pFixed.y + newH / 2,
            x: currentVp.x,
          });
        } else if (interactionMode === 'ZOOMING_LEFT') {
          pFixed = { x: currentVp.x + currentVW / 2, y: currentVp.y };
          const newW = Math.max(10, Math.abs(worldPos.x - pFixed.x));
          const newZoom = projW / newW;
          setDragState({
            zoom: newZoom,
            x: pFixed.x - newW / 2,
            y: currentVp.y,
          });
        } else if (interactionMode === 'ZOOMING_RIGHT') {
          pFixed = { x: currentVp.x - currentVW / 2, y: currentVp.y };
          const newW = Math.max(10, Math.abs(worldPos.x - pFixed.x));
          const newZoom = projW / newW;
          setDragState({
            zoom: newZoom,
            x: pFixed.x + newW / 2,
            y: currentVp.y,
          });
        }
      }
    },
    [interactionMode, currentVp, projW, projH, grid_spacing_svg, screenToWorld]
  );

  const handleMouseUp = useCallback(async () => {
    if (interactionMode === 'IDLE') return;

    const finalState = dragState;
    setInteractionMode('IDLE');

    try {
      await setViewportConfig(finalState.x, finalState.y, finalState.zoom, currentVp.rotation);
    } catch (err) {
      console.error('Failed to save viewport config:', err);
    }
  }, [interactionMode, dragState, currentVp.rotation]);

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

  if (!isConnected || !isVisible) return null;

  return (
    <g ref={groupRef}>
      {/* Viewport Rectangle */}
      <rect
        x={xMin}
        y={yMin}
        width={vW}
        height={vH}
        fill="rgba(79, 70, 229, 0.1)"
        stroke="#4f46e5"
        strokeWidth="2"
        strokeDasharray="5,5"
        pointerEvents="none"
      />

      {/* Center Pan Handle */}
      <circle
        cx={displayedVp.x}
        cy={displayedVp.y}
        r="12"
        fill="white"
        stroke="#22c55e"
        strokeWidth="3"
        cursor="move"
        onMouseDown={handleMouseDownCenter}
        className="shadow-sm"
      />
      <circle
        cx={displayedVp.x}
        cy={displayedVp.y}
        r="4"
        fill="#22c55e"
        pointerEvents="none"
      />

      {/* Zoom Handles (Midpoints) */}
      {/* Top */}
      <circle
        cx={displayedVp.x}
        cy={yMin}
        r="8"
        fill="white"
        stroke="#4f46e5"
        strokeWidth="2"
        cursor="ns-resize"
        onMouseDown={(e) => handleMouseDownSide(e, 'ZOOMING_TOP')}
      />
      {/* Bottom */}
      <circle
        cx={displayedVp.x}
        cy={yMin + vH}
        r="8"
        fill="white"
        stroke="#4f46e5"
        strokeWidth="2"
        cursor="ns-resize"
        onMouseDown={(e) => handleMouseDownSide(e, 'ZOOMING_BOTTOM')}
      />
      {/* Left */}
      <circle
        cx={xMin}
        cy={displayedVp.y}
        r="8"
        fill="white"
        stroke="#4f46e5"
        strokeWidth="2"
        cursor="ew-resize"
        onMouseDown={(e) => handleMouseDownSide(e, 'ZOOMING_LEFT')}
      />
      {/* Right */}
      <circle
        cx={xMin + vW}
        cy={displayedVp.y}
        r="8"
        fill="white"
        stroke="#4f46e5"
        strokeWidth="2"
        cursor="ew-resize"
        onMouseDown={(e) => handleMouseDownSide(e, 'ZOOMING_RIGHT')}
      />
    </g>
  );
};
