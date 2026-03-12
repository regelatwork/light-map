/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useContext, type ReactNode } from 'react';

interface CanvasContextType {
  screenToWorld: (clientX: number, clientY: number) => { x: number; y: number } | null;
}

const CanvasContext = createContext<CanvasContextType | null>(null);

export const useCanvas = () => {
  const context = useContext(CanvasContext);
  if (!context) {
    throw new Error('useCanvas must be used within a CanvasProvider');
  }
  return context;
};

interface CanvasProviderProps {
  children: ReactNode;
  svgRef: React.RefObject<SVGSVGElement | null>;
  viewBox: { x: number; y: number; w: number; h: number };
  rotation?: number;
  centerX?: number;
  centerY?: number;
}

export const CanvasProvider: React.FC<CanvasProviderProps> = ({
  children,
  svgRef,
  viewBox,
  rotation = 0,
  centerX = 0,
  centerY = 0,
}) => {
  const screenToWorld = (clientX: number, clientY: number) => {
    const svg = svgRef.current;
    if (!svg) return null;

    const rect = svg.getBoundingClientRect();
    const mouseX = clientX - rect.left;
    const mouseY = clientY - rect.top;

    const x_svg = viewBox.x + (mouseX * viewBox.w) / rect.width;
    const y_svg = viewBox.y + (mouseY * viewBox.h) / rect.height;

    if (rotation === 0) {
      return { x: x_svg, y: y_svg };
    }

    // Rotate point BACKWARDS around center to get world coordinates
    const angleRad = (-rotation * Math.PI) / 180;
    const dx = x_svg - centerX;
    const dy = y_svg - centerY;

    const x = dx * Math.cos(angleRad) - dy * Math.sin(angleRad) + centerX;
    const y = dx * Math.sin(angleRad) + dy * Math.cos(angleRad) + centerY;

    return { x, y };
  };

  return <CanvasContext.Provider value={{ screenToWorld }}>{children}</CanvasContext.Provider>;
};
