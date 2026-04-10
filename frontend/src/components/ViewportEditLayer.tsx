import React, { useState, useEffect, useCallback } from 'react';
import { useSystemState } from '../hooks/useSystemState';
import { useCanvas } from './CanvasContext';
import { useCalibration, CalibrationMode } from './CalibrationContext';
import { setViewportConfig } from '../services/api';

type InteractionMode = 'IDLE' | 'PANNING' | 'ZOOMING_TOP' | 'ZOOMING_BOTTOM' | 'ZOOMING_LEFT' | 'ZOOMING_RIGHT';

export const ViewportEditLayer: React.FC = () => {
  const { world, config, grid_spacing_svg } = useSystemState();
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
  const safeZoom = Math.max(0.001, displayedVp.zoom || 1.0);

  const projW = config.proj_res?.[0] || 1920;
  const projH = config.proj_res?.[1] || 1080;

  // In the backend, P_screen = Translate( Rotate_around_center( Scale( P_world ) ) )
  // So P_world = Scale_inv( Rotate_inv_around_center( P_screen - Translate ) )
  // To get the viewport center in world space (where P_screen = center):
  // We need to account for the fact that we are INSIDE the rotated group in SchematicCanvas.
  // The group is rotated around (projW/2, projH/2) by 'rotation'.
  
  // If we are inside the group, we just need to handle Translation and Scale.
  // Center in world space:
  const vCenterX = (projW / 2 - (displayedVp.x || 0)) / safeZoom;
  const vCenterY = (projH / 2 - (displayedVp.y || 0)) / safeZoom;

  // Viewport dimensions in world space
  const vW = projW / safeZoom;
  const vH = projH / safeZoom;

  // Rectangle bounds
  const xMin = vCenterX - vW / 2;
  const yMin = vCenterY - vH / 2;

  useEffect(() => {
    if (isVisible) {
      console.log('ViewportEditLayer Visible:', {
        isVisible,
        currentVp,
        projW,
        projH,
        vCenterX,
        vCenterY,
        vW,
        vH,
        xMin,
        yMin
      });
    }
  }, [isVisible, currentVp, projW, projH, vCenterX, vCenterY, vW, vH, xMin, yMin]);

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
        // Translation change
        // sx = Zoom * wx + tx  => tx = sx - Zoom * wx
        // We want sx = projW/2, sy = projH/2
        const spacing = grid_spacing_svg || 1;
        const snappedWx = Math.round(worldPos.x / spacing) * spacing;
        const snappedWy = Math.round(worldPos.y / spacing) * spacing;
        
        const newTx = projW / 2 - displayedVp.zoom * snappedWx;
        const newTy = projH / 2 - displayedVp.zoom * snappedWy;
        
        setDragState((prev) => ({ ...prev, x: newTx, y: newTy }));
      } else {
        // Zooming logic - Opposite Side Fixed
        const currentVW = projW / currentVp.zoom;
        const currentVH = projH / currentVp.zoom;
        
        // P_fixed in world space
        let pFixed = { x: vCenterX, y: vCenterY };

        if (interactionMode === 'ZOOMING_TOP') {
          pFixed = { x: vCenterX, y: vCenterY + currentVH / 2 };
          const newH = Math.max(10, Math.abs(worldPos.y - pFixed.y));
          const newZoom = projH / newH;
          // New Center Y in world space
          const newVcy = pFixed.y - newH / 2;
          // ty = projH/2 - newZoom * newVcy
          setDragState({
            zoom: newZoom,
            y: projH / 2 - newZoom * newVcy,
            x: projW / 2 - newZoom * vCenterX,
          });
        } else if (interactionMode === 'ZOOMING_BOTTOM') {
          pFixed = { x: vCenterX, y: vCenterY - currentVH / 2 };
          const newH = Math.max(10, Math.abs(worldPos.y - pFixed.y));
          const newZoom = projH / newH;
          const newVcy = pFixed.y + newH / 2;
          setDragState({
            zoom: newZoom,
            y: projH / 2 - newZoom * newVcy,
            x: projW / 2 - newZoom * vCenterX,
          });
        } else if (interactionMode === 'ZOOMING_LEFT') {
          pFixed = { x: vCenterX + currentVW / 2, y: vCenterY };
          const newW = Math.max(10, Math.abs(worldPos.x - pFixed.x));
          const newZoom = projW / newW;
          const newVcx = pFixed.x - newW / 2;
          setDragState({
            zoom: newZoom,
            x: projW / 2 - newZoom * newVcx,
            y: projH / 2 - newZoom * vCenterY,
          });
        } else if (interactionMode === 'ZOOMING_RIGHT') {
          pFixed = { x: vCenterX - currentVW / 2, y: vCenterY };
          const newW = Math.max(10, Math.abs(worldPos.x - pFixed.x));
          const newZoom = projW / newW;
          const newVcx = pFixed.x + newW / 2;
          setDragState({
            zoom: newZoom,
            x: projW / 2 - newZoom * newVcx,
            y: projH / 2 - newZoom * vCenterY,
          });
        }
      }
    },
    [interactionMode, currentVp, projW, projH, grid_spacing_svg, screenToWorld, vCenterX, vCenterY, displayedVp.zoom]
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

  if (!isVisible) return null;

  return (
    <g ref={groupRef}>
      {/* Viewport Rectangle */}
      <rect
        x={xMin}
        y={yMin}
        width={vW}
        height={vH}
        fill="rgba(254, 240, 138, 0.2)"
        stroke="#facc15"
        strokeWidth="4"
        strokeDasharray="10,5"
        pointerEvents="none"
      />

      {/* Center Pan Handle */}
      <circle
        cx={vCenterX}
        cy={vCenterY}
        r="16"
        fill="white"
        stroke="#22c55e"
        strokeWidth="4"
        cursor="move"
        onMouseDown={handleMouseDownCenter}
        className="shadow-lg"
      />
      <circle
        cx={vCenterX}
        cy={vCenterY}
        r="6"
        fill="#22c55e"
        pointerEvents="none"
      />

      {/* Zoom Handles (Midpoints) */}
      {/* Top */}
      <circle
        cx={vCenterX}
        cy={yMin}
        r="12"
        fill="white"
        stroke="#facc15"
        strokeWidth="4"
        cursor="ns-resize"
        onMouseDown={(e) => handleMouseDownSide(e, 'ZOOMING_TOP')}
      />
      {/* Bottom */}
      <circle
        cx={vCenterX}
        cy={yMin + vH}
        r="12"
        fill="white"
        stroke="#facc15"
        strokeWidth="4"
        cursor="ns-resize"
        onMouseDown={(e) => handleMouseDownSide(e, 'ZOOMING_BOTTOM')}
      />
      {/* Left */}
      <circle
        cx={xMin}
        cy={vCenterY}
        r="12"
        fill="white"
        stroke="#facc15"
        strokeWidth="4"
        cursor="ew-resize"
        onMouseDown={(e) => handleMouseDownSide(e, 'ZOOMING_LEFT')}
      />
      {/* Right */}
      <circle
        cx={xMin + vW}
        cy={vCenterY}
        r="12"
        fill="white"
        stroke="#facc15"
        strokeWidth="4"
        cursor="ew-resize"
        onMouseDown={(e) => handleMouseDownSide(e, 'ZOOMING_RIGHT')}
      />
    </g>
  );
};
