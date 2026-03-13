import { useState, useRef, useEffect, type ReactNode, type FC } from 'react';
import { GridLayer } from './GridLayer';
import { TokenLayer } from './TokenLayer';
import { MapLayer } from './MapLayer';
import { DoorLayer } from './DoorLayer';
import { FowLayer } from './FowLayer';
import { CanvasProvider } from './CanvasContext';
import { useSelection } from './SelectionContext';
import { useGridEdit } from './GridEditContext';
import { useSystemState } from '../hooks/useSystemState';
import { SelectionType } from '../types/system';

interface SchematicCanvasProps {
  children?: ReactNode;
}

export const SchematicCanvas: FC<SchematicCanvasProps> = ({ children }) => {
  const { world, config, grid_origin_svg_x, grid_origin_svg_y } = useSystemState();
  const { isGridEditMode } = useGridEdit();
  const rotation = world.viewport?.rotation || 0;
  const centerX = (config.proj_res?.[0] || 1000) / 2;
  const centerY = (config.proj_res?.[1] || 750) / 2;

  // Viewbox state (x, y, width, height)
  // Start with (0,0) in the center of a 1000x750 view
  const [viewBox, setViewBox] = useState({ x: -500, y: -375, w: 1000, h: 750 });
  const isPanning = useRef(false);
  const startPoint = useRef({ x: 0, y: 0 });
  const svgRef = useRef<SVGSVGElement>(null);
  const { setSelection } = useSelection();

  // Use a ref to ensure we only do the initial centering once
  const initialCentered = useRef(false);

  useEffect(() => {
    if (world.scene !== 'LOADING' && !initialCentered.current) {
      setViewBox((prev) => ({
        ...prev,
        x: (grid_origin_svg_x || 0) - prev.w / 2,
        y: (grid_origin_svg_y || 0) - prev.h / 2,
      }));
      initialCentered.current = true;
    }
  }, [world.scene, grid_origin_svg_x, grid_origin_svg_y]);

  const handleMouseDown = (e: React.MouseEvent) => {
    // Only pan if we didn't click an interactive element (handled by layers)
    if (
      e.button === 0 &&
      (e.target === svgRef.current || (e.target as Element).tagName === 'rect')
    ) {
      isPanning.current = true;
      startPoint.current = { x: e.clientX, y: e.clientY };
    }
  };

  const handleBackgroundClick = () => {
    // Clear selection when clicking the background
    setSelection({ type: SelectionType.NONE, id: null });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isPanning.current) return;

    const dx = e.clientX - startPoint.current.x;
    const dy = e.clientY - startPoint.current.y;

    // Scale movement by the current zoom level
    const scale = viewBox.w / (svgRef.current?.clientWidth || 1000);

    setViewBox((prev) => ({
      ...prev,
      x: prev.x - dx * scale,
      y: prev.y - dy * scale,
    }));

    startPoint.current = { x: e.clientX, y: e.clientY };
  };

  const handleMouseUp = () => {
    isPanning.current = false;
  };

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const zoomIntensity = 0.1;
    const delta = e.deltaY > 0 ? 1 + zoomIntensity : 1 - zoomIntensity;

    // Zoom relative to mouse position
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return;

    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    // Convert mouse position to SVG coordinates
    const svgX = viewBox.x + (mouseX * viewBox.w) / rect.width;
    const svgY = viewBox.y + (mouseY * viewBox.h) / rect.height;

    const newW = viewBox.w * delta;
    const newH = viewBox.h * delta;

    // Adjust x and y so the point under the mouse stays stationary
    const newX = svgX - (mouseX * newW) / rect.width;
    const newY = svgY - (mouseY * newH) / rect.height;

    setViewBox({
      x: newX,
      y: newY,
      w: newW,
      h: newH,
    });
  };

  const resetView = () => {
    setViewBox({
      x: (grid_origin_svg_x || 0) - 500,
      y: (grid_origin_svg_y || 0) - 375,
      w: 1000,
      h: 750,
    });
  };

  return (
    <div className="relative h-full w-full overflow-hidden bg-white border-2 border-gray-200 rounded-lg shadow-inner text-black">
      <CanvasProvider
        svgRef={svgRef}
        viewBox={viewBox}
        rotation={rotation}
        centerX={centerX}
        centerY={centerY}
      >
        <svg
          ref={svgRef}
          className="h-full w-full cursor-move select-none"
          viewBox={`${viewBox.x} ${viewBox.y} ${viewBox.w} ${viewBox.h}`}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          onWheel={handleWheel}
        >
          {/* Background layer */}
          <rect
            x={viewBox.x}
            y={viewBox.y}
            width={viewBox.w}
            height={viewBox.h}
            fill="#f9fafb"
            onClick={handleBackgroundClick}
          />

          <g transform={`rotate(${rotation}, ${centerX}, ${centerY})`}>
            <MapLayer />
            <DoorLayer />
            <GridLayer />
            <TokenLayer />
            {!isGridEditMode && <FowLayer />}

            {/* Layers will be rendered as children */}
            {children}
          </g>
        </svg>
      </CanvasProvider>

      {/* Control overlay */}
      <div className="absolute bottom-4 right-4 flex flex-col gap-2">
        <button
          onClick={resetView}
          className="rounded bg-white px-3 py-1 text-sm font-medium shadow hover:bg-gray-50 text-black border border-gray-300"
        >
          Reset View
        </button>
      </div>
    </div>
  );
};
