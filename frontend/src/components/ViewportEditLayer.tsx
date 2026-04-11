import React, { useState, useEffect, useCallback } from 'react';
import { useSystemState } from '../hooks/useSystemState';
import { useCanvas } from './CanvasContext';
import { useCalibration, CalibrationMode } from './CalibrationContext';
import { setViewportConfig } from '../services/api';
import { rotatePoint } from '../utils/geometry';

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
    rotation: 0,
  });
  const [fixedPoint, setFixedPoint] = useState<{ x: number, y: number } | null>(null);

  const currentVp = React.useMemo(() => 
    world.viewport || { x: 0, y: 0, zoom: 1.0, rotation: 0 },
    [world.viewport]
  );
  
  const displayedVp = React.useMemo(() => 
    interactionMode !== 'IDLE' ? dragState : currentVp,
    [interactionMode, dragState, currentVp]
  );
  const safeZoom = Math.max(0.001, displayedVp.zoom || 1.0);

  // Use same defaults as SchematicCanvas for consistency
  const projW = config.proj_res?.[0] || 1000;
  const projH = config.proj_res?.[1] || 750;
  const centerX = projW / 2;
  const centerY = projH / 2;
  const rotation = displayedVp.rotation || 0;

  // Function to map screen coordinates to world coordinates (inverting the projection)
  // P_screen = T + R_center(Zoom * P_world)
  // P_world = R_center_inv(P_screen - T) / Zoom
  const getW = useCallback((sx: number, sy: number, vpX: number, vpY: number, vpZoom: number, vpRot: number) => {
    const p = rotatePoint(sx - vpX, sy - vpY, centerX, centerY, -vpRot);
    return { x: p.x / vpZoom, y: p.y / vpZoom };
  }, [centerX, centerY]);

  // Viewport corners and midpoints in world space
  const wTL = getW(0, 0, displayedVp.x, displayedVp.y, safeZoom, rotation);
  const wTR = getW(projW, 0, displayedVp.x, displayedVp.y, safeZoom, rotation);
  const wBR = getW(projW, projH, displayedVp.x, displayedVp.y, safeZoom, rotation);
  const wBL = getW(0, projH, displayedVp.x, displayedVp.y, safeZoom, rotation);
  
  const wTop = getW(centerX, 0, displayedVp.x, displayedVp.y, safeZoom, rotation);
  const wBottom = getW(centerX, projH, displayedVp.x, displayedVp.y, safeZoom, rotation);
  const wLeft = getW(0, centerY, displayedVp.x, displayedVp.y, safeZoom, rotation);
  const wRight = getW(projW, centerY, displayedVp.x, displayedVp.y, safeZoom, rotation);
  const wCenter = getW(centerX, centerY, displayedVp.x, displayedVp.y, safeZoom, rotation);

  const handleMouseDownCenter = (e: React.MouseEvent) => {
    e.stopPropagation();
    setInteractionMode('PANNING');
    setDragState({ x: currentVp.x, y: currentVp.y, zoom: currentVp.zoom, rotation: currentVp.rotation });
  };

  const handleMouseDownSide = (e: React.MouseEvent, mode: InteractionMode) => {
    e.stopPropagation();
    
    // Fixed screen point for each handle (the opposite side)
    let Sf = { x: centerX, y: centerY };
    if (mode === 'ZOOMING_TOP') Sf = { x: centerX, y: projH };
    if (mode === 'ZOOMING_BOTTOM') Sf = { x: centerX, y: 0 };
    if (mode === 'ZOOMING_LEFT') Sf = { x: projW, y: centerY };
    if (mode === 'ZOOMING_RIGHT') Sf = { x: 0, y: centerY };

    // Calculate initial world coordinate for this fixed point
    const Wf = getW(Sf.x, Sf.y, currentVp.x, currentVp.y, currentVp.zoom, currentVp.rotation);

    setFixedPoint(Wf);
    setInteractionMode(mode);
    setDragState({ x: currentVp.x, y: currentVp.y, zoom: currentVp.zoom, rotation: currentVp.rotation });
  };

  const handleMouseMove = useCallback(
    (e: MouseEvent) => {
      if (interactionMode === 'IDLE') return;

      const worldPos = screenToWorld(e.clientX, e.clientY, groupRef.current || undefined);
      if (!worldPos) return;

      if (interactionMode === 'PANNING') {
        const spacing = grid_spacing_svg || 1;
        const snappedWx = Math.round(worldPos.x / spacing) * spacing;
        const snappedWy = Math.round(worldPos.y / spacing) * spacing;
        
        // We want the snapped world point to be at the center of the screen
        const rotatedSnappedW = rotatePoint(
          currentVp.zoom * snappedWx,
          currentVp.zoom * snappedWy,
          centerX,
          centerY,
          currentVp.rotation
        );
        const newTx = centerX - rotatedSnappedW.x;
        const newTy = centerY - rotatedSnappedW.y;
        
        setDragState((prev) => ({ ...prev, x: newTx, y: newTy }));
      } else if (fixedPoint) {
        // Zooming logic - Opposite Side Fixed
        let Sf = { x: centerX, y: centerY };
        let targetDist = 0;
        let isVertical = false;

        if (interactionMode === 'ZOOMING_TOP') { Sf = { x: centerX, y: projH }; targetDist = projH; isVertical = true; }
        if (interactionMode === 'ZOOMING_BOTTOM') { Sf = { x: centerX, y: 0 }; targetDist = projH; isVertical = true; }
        if (interactionMode === 'ZOOMING_LEFT') { Sf = { x: projW, y: centerY }; targetDist = projW; isVertical = false; }
        if (interactionMode === 'ZOOMING_RIGHT') { Sf = { x: 0, y: centerY }; targetDist = projW; isVertical = false; }

        // Vector from fixed point to mouse in world space
        const vWorld = { x: worldPos.x - fixedPoint.x, y: worldPos.y - fixedPoint.y };
        // Rotate back to screen-aligned coordinates
        const vScreenDir = rotatePoint(vWorld.x, vWorld.y, 0, 0, currentVp.rotation);
        
        // Distance in world space along the relevant screen axis
        const distWorld = Math.max(10 / currentVp.zoom, isVertical ? Math.abs(vScreenDir.y) : Math.abs(vScreenDir.x));
        
        const newZoom = targetDist / distWorld;
        
        // Keep the fixed world point at its fixed screen position: T = Sf - R(Z_new * Wf)
        const rotatedWf = rotatePoint(newZoom * fixedPoint.x, newZoom * fixedPoint.y, centerX, centerY, currentVp.rotation);
        const newTx = Sf.x - rotatedWf.x;
        const newTy = Sf.y - rotatedWf.y;
        
        setDragState({ zoom: newZoom, x: newTx, y: newTy, rotation: currentVp.rotation });
      }
    },
    [interactionMode, currentVp, centerX, centerY, projW, projH, grid_spacing_svg, screenToWorld, fixedPoint]
  );

  const handleMouseUp = useCallback(async () => {
    if (interactionMode === 'IDLE') return;

    const finalState = dragState;
    setInteractionMode('IDLE');
    setFixedPoint(null);

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
      {/* Viewport Polygon */}
      <polygon
        points={`${wTL.x},${wTL.y} ${wTR.x},${wTR.y} ${wBR.x},${wBR.y} ${wBL.x},${wBL.y}`}
        fill="rgba(254, 240, 138, 0.2)"
        stroke="#facc15"
        strokeWidth={4 / safeZoom}
        strokeDasharray={`${10 / safeZoom},${5 / safeZoom}`}
        pointerEvents="none"
      />

      {/* Center Pan Handle */}
      <circle
        cx={wCenter.x}
        cy={wCenter.y}
        r={16 / safeZoom}
        fill="white"
        stroke="#22c55e"
        strokeWidth={4 / safeZoom}
        cursor="move"
        onMouseDown={handleMouseDownCenter}
        className="shadow-lg"
      />
      <circle
        cx={wCenter.x}
        cy={wCenter.y}
        r={6 / safeZoom}
        fill="#22c55e"
        pointerEvents="none"
      />

      {/* Zoom Handles (Midpoints) */}
      {/* Top */}
      <circle
        cx={wTop.x}
        cy={wTop.y}
        r={12 / safeZoom}
        fill="white"
        stroke="#facc15"
        strokeWidth={4 / safeZoom}
        cursor="ns-resize"
        onMouseDown={(e) => handleMouseDownSide(e, 'ZOOMING_TOP')}
      />
      {/* Bottom */}
      <circle
        cx={wBottom.x}
        cy={wBottom.y}
        r={12 / safeZoom}
        fill="white"
        stroke="#facc15"
        strokeWidth={4 / safeZoom}
        cursor="ns-resize"
        onMouseDown={(e) => handleMouseDownSide(e, 'ZOOMING_BOTTOM')}
      />
      {/* Left */}
      <circle
        cx={wLeft.x}
        cy={wLeft.y}
        r={12 / safeZoom}
        fill="white"
        stroke="#facc15"
        strokeWidth={4 / safeZoom}
        cursor="ew-resize"
        onMouseDown={(e) => handleMouseDownSide(e, 'ZOOMING_LEFT')}
      />
      {/* Right */}
      <circle
        cx={wRight.x}
        cy={wRight.y}
        r={12 / safeZoom}
        fill="white"
        stroke="#facc15"
        strokeWidth={4 / safeZoom}
        cursor="ew-resize"
        onMouseDown={(e) => handleMouseDownSide(e, 'ZOOMING_RIGHT')}
      />
    </g>
  );
};
