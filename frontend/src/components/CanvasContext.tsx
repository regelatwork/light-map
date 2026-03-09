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
}

export const CanvasProvider: React.FC<CanvasProviderProps> = ({ children, svgRef, viewBox }) => {
  const screenToWorld = (clientX: number, clientY: number) => {
    const svg = svgRef.current;
    if (!svg) return null;

    const rect = svg.getBoundingClientRect();
    const mouseX = clientX - rect.left;
    const mouseY = clientY - rect.top;

    const x = viewBox.x + (mouseX * viewBox.w) / rect.width;
    const y = viewBox.y + (mouseY * viewBox.h) / rect.height;

    return { x, y };
  };

  return <CanvasContext.Provider value={{ screenToWorld }}>{children}</CanvasContext.Provider>;
};
