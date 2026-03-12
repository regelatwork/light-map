import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { CanvasProvider, useCanvas } from './CanvasContext';

const TestComponent = ({ clientX, clientY }: { clientX: number; clientY: number }) => {
  const { screenToWorld } = useCanvas();
  const worldPos = screenToWorld(clientX, clientY);
  return (
    <div data-testid="world-pos">
      {worldPos ? `${Math.round(worldPos.x)},${Math.round(worldPos.y)}` : 'null'}
    </div>
  );
};

describe('CanvasProvider', () => {
  const mockSvg = {
    getBoundingClientRect: () => ({
      left: 0,
      top: 0,
      width: 1000,
      height: 750,
    }),
  } as unknown as SVGSVGElement;

  const svgRef = { current: mockSvg };
  const viewBox = { x: 0, y: 0, w: 1000, h: 750 };

  it('correctly maps screen to world without rotation', () => {
    render(
      <CanvasProvider svgRef={svgRef} viewBox={viewBox}>
        <TestComponent clientX={500} clientY={375} />
      </CanvasProvider>
    );
    expect(screen.getByTestId('world-pos')).toHaveTextContent('500,375');
  });

  it('correctly maps screen to world with 90 degree rotation', () => {
    // Rotation 90 around (500, 375)
    // World (600, 375) -> SVG (500, 475)
    // Screen (500, 475) -> SVG (500, 475) -> World (600, 375)
    render(
      <CanvasProvider
        svgRef={svgRef}
        viewBox={viewBox}
        rotation={90}
        centerX={500}
        centerY={375}
      >
        <TestComponent clientX={500} clientY={475} />
      </CanvasProvider>
    );
    expect(screen.getByTestId('world-pos')).toHaveTextContent('600,375');
  });

  it('correctly maps screen to world with 180 degree rotation', () => {
    // Rotation 180 around (500, 375)
    // World (600, 475) -> SVG (400, 275)
    // Screen (400, 275) -> SVG (400, 275) -> World (600, 475)
    render(
      <CanvasProvider
        svgRef={svgRef}
        viewBox={viewBox}
        rotation={180}
        centerX={500}
        centerY={375}
      >
        <TestComponent clientX={400} clientY={275} />
      </CanvasProvider>
    );
    expect(screen.getByTestId('world-pos')).toHaveTextContent('600,475');
  });
});
