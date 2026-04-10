import { render, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ViewportEditLayer } from './ViewportEditLayer';
import { CalibrationProvider, CalibrationMode, useCalibration } from './CalibrationContext';
import * as api from '../services/api';

const EnableViewportEdit = ({ children }: { children: React.ReactNode }) => {
  const { setMode } = useCalibration();
  React.useEffect(() => {
    setMode(CalibrationMode.VIEWPORT);
  }, [setMode]);
  return <>{children}</>;
};

// Mock useSystemState
vi.mock('../hooks/useSystemState', () => ({
  useSystemState: () => ({
    isConnected: true,
    grid_spacing_svg: 50,
    config: {
      proj_res: [1000, 500],
    },
    world: {
      viewport: { x: 500, y: 250, zoom: 1.0, rotation: 0 },
    },
  }),
}));

// Mock useCanvas
vi.mock('./CanvasContext', () => ({
  useCanvas: () => ({
    screenToWorld: (x: number, y: number) => ({ x, y }),
  }),
  CanvasProvider: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

// Mock API service
vi.mock('../services/api', () => ({
  setViewportConfig: vi.fn().mockResolvedValue({ status: 'ok' }),
}));

describe('ViewportEditLayer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders viewport rectangle and handles at correct world positions', () => {
    const { container } = render(
      <CalibrationProvider>
        <EnableViewportEdit>
          <svg>
            <ViewportEditLayer />
          </svg>
        </EnableViewportEdit>
      </CalibrationProvider>
    );

    // Initial translation (500, 250) at zoom 1.0 means world origin (0,0) is at screen center (500, 250).
    // So viewport center in world space is (0,0).
    // Viewport width = 1000, height = 500.
    // xMin = -500, yMin = -250.
    
    const rect = container.querySelector('rect');
    expect(rect).toBeInTheDocument();
    expect(rect).toHaveAttribute('width', '1000');
    expect(rect).toHaveAttribute('height', '500');
    expect(rect).toHaveAttribute('x', '-500');
    expect(rect).toHaveAttribute('y', '-250');

    // Handles should be at world coordinates
    const circles = container.querySelectorAll('circle');
    // center pan handle (vCenterX, vCenterY) = (0, 0)
    expect(circles[0]).toHaveAttribute('cx', '0');
    expect(circles[0]).toHaveAttribute('cy', '0');
  });

  it('calculates new translation when panning', async () => {
    const { container } = render(
      <CalibrationProvider>
        <EnableViewportEdit>
          <svg>
            <ViewportEditLayer />
          </svg>
        </EnableViewportEdit>
      </CalibrationProvider>
    );

    const centerHandle = container.querySelectorAll('circle')[0];

    // Start drag
    fireEvent.mouseDown(centerHandle);

    // Drag from (0,0) world to (550, 300) world.
    // New translation: tx = 500 - 1.0 * 550 = -50, ty = 250 - 1.0 * 300 = -50.
    fireEvent.mouseMove(window, { clientX: 550, clientY: 300 });

    // Stop drag
    fireEvent.mouseUp(window);

    await waitFor(() => {
      expect(api.setViewportConfig).toHaveBeenCalledWith(-50, -50, 1.0, 0);
    });
  });

  it('calculates new zoom and translation when dragging top handle', async () => {
    const { container } = render(
      <CalibrationProvider>
        <EnableViewportEdit>
          <svg>
            <ViewportEditLayer />
          </svg>
        </EnableViewportEdit>
      </CalibrationProvider>
    );

    // Top handle is circles[2]
    const topHandle = container.querySelectorAll('circle')[2];

    // Start drag
    fireEvent.mouseDown(topHandle);

    // Drag Top handle downwards.
    // Fixed point is bottom midpoint: (0, 250) world space.
    // Target drag position (screen 500, 375 maps to world 500, 375 in our simple mock).
    // Wait, let's use a more realistic drag.
    // Original Top Y was -250. Let's drag to world Y = 0.
    // New height = abs(0 - 250) = 250.
    // New Zoom = 500 / 250 = 2.0.
    // New Center Y in world = 250 - 250 / 2 = 125.
    // ty = 250 - 2.0 * 125 = 0.
    // tx = 500 - 2.0 * 0 = 500.
    fireEvent.mouseMove(window, { clientX: 500, clientY: 0 });

    // Stop drag
    fireEvent.mouseUp(window);

    await waitFor(() => {
      expect(api.setViewportConfig).toHaveBeenCalledWith(500, 0, 2.0, 0);
    });
  });
});
