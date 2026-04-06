/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useContext, useCallback, type ReactNode } from 'react';
import { rotatePoint } from '../utils/geometry';

interface CanvasContextType {
  screenToWorld: (
    clientX: number,
    clientY: number,
    element?: SVGGraphicsElement
  ) => { x: number; y: number } | null;
  worldToSVG: (x: number, y: number) => { x: number; y: number };
  svgToWorld: (x: number, y: number) => { x: number; y: number };
}

const CanvasContext = createContext<CanvasContextType | null>(null);

export const useCanvas = () => {
  const context = useContext(CanvasContext);
  if (!context) {
    throw new Error('useCanvas must be used within a CanvasProvider');
  }
  return context;
};

export interface CanvasProviderProps {
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
  const worldToSVG = useCallback(
    (x: number, y: number) => rotatePoint(x, y, centerX, centerY, rotation),
    [centerX, centerY, rotation]
  );

  const svgToWorld = useCallback(
    (x: number, y: number) => rotatePoint(x, y, centerX, centerY, -rotation),
    [centerX, centerY, rotation]
  );

  const screenToWorld = useCallback(
    (clientX: number, clientY: number, element?: SVGGraphicsElement) => {
      const svg = svgRef.current;
      if (!svg) return null;

      try {
        if (element) {
          const pt = svg.createSVGPoint();
          pt.x = clientX;
          pt.y = clientY;
          const ctm = element.getScreenCTM();
          if (ctm) {
            const localPt = pt.matrixTransform(ctm.inverse());
            return { x: localPt.x, y: localPt.y };
          }
        }

        const rect = svg.getBoundingClientRect();
        const x_svg = viewBox.x + ((clientX - rect.left) * viewBox.w) / rect.width;
        const y_svg = viewBox.y + ((clientY - rect.top) * viewBox.h) / rect.height;

        return svgToWorld(x_svg, y_svg);
      } catch (err) {
        console.error('screenToWorld error:', err);
        return null;
      }
    },
    [svgRef, viewBox, svgToWorld]
  );

  return (
    <CanvasContext.Provider value={{ screenToWorld, worldToSVG, svgToWorld }}>
      {children}
    </CanvasContext.Provider>
  );
};
