import React, { useState, useRef, type ReactNode } from 'react';
import { GridLayer } from './GridLayer';
import { TokenLayer } from './TokenLayer';
import { MapLayer } from './MapLayer';
import { DoorLayer } from './DoorLayer';
import { FowLayer } from './FowLayer';
import { CanvasProvider } from './CanvasContext';
import { useSelection } from './SelectionContext';

interface SchematicCanvasProps {
  children?: ReactNode;
}

export const SchematicCanvas: React.FC<SchematicCanvasProps> = ({ children }) => {
  // Viewbox state (x, y, width, height)
  const [viewBox, setViewBox] = useState({ x: 0, y: 0, w: 1000, h: 750 });
  const [isPanning, setIsPanning] = useState(false);
  const svgRef = useRef<SVGSVGElement>(null);
  const startPoint = useRef({ x: 0, y: 0 });
  const { setSelection } = useSelection();

  const handleMouseDown = (e: React.MouseEvent) => {
    // Only pan if we didn't click an interactive element (handled by layers)
    if (e.button === 0 && (e.target === svgRef.current || (e.target as Element).tagName === 'rect')) {
      setIsPanning(true);
      startPoint.current = { x: e.clientX, y: e.clientY };
    }
  };

  const handleBackgroundClick = () => {
    // Clear selection when clicking the background
    setSelection({ type: 'none', id: null });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isPanning) return;

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
    setIsPanning(false);
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

  return (
    <div className="relative h-full w-full overflow-hidden bg-white border-2 border-gray-200 rounded-lg shadow-inner text-black">
      <CanvasProvider svgRef={svgRef} viewBox={viewBox}>
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

          <MapLayer />
          <DoorLayer />
          <GridLayer />
          <TokenLayer />
          <FowLayer />

          {/* Layers will be rendered as children */}
          {children}
        </svg>
      </CanvasProvider>

      {/* Control overlay */}
      <div className="absolute bottom-4 right-4 flex flex-col gap-2">
        <button
          onClick={() => setViewBox({ x: 0, y: 0, w: 1000, h: 750 })}
          className="rounded bg-white px-3 py-1 text-sm font-medium shadow hover:bg-gray-50 text-black border border-gray-300"
        >
          Reset View
        </button>
      </div>
    </div>
  );
};
