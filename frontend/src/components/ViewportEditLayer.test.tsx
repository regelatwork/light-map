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

  it('renders viewport rectangle and handles', () => {
    const { container } = render(
      <CalibrationProvider>
        <EnableViewportEdit>
          <svg>
            <ViewportEditLayer />
          </svg>
        </EnableViewportEdit>
      </CalibrationProvider>
    );

    // Should have viewport rect
    const rect = container.querySelector('rect');
    expect(rect).toBeInTheDocument();
    // width = 1000 / 1.0 = 1000, height = 500 / 1.0 = 500
    // centered at 500, 250 => xMin = 0, yMin = 0
    expect(rect).toHaveAttribute('width', '1000');
    expect(rect).toHaveAttribute('height', '500');

    // Should have 1 pan handle + 4 zoom handles = 5 handles
    const circles = container.querySelectorAll('circle');
    expect(circles.length).toBe(6); // 2 for center pan (outer+inner) + 4 for zoom
  });

  it('calls setViewportConfig when dragging center handle', async () => {
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

    // Move mouse (origin 500, 250 -> move to 550, 300)
    // grid_spacing_svg is 50, so this is exactly one grid unit
    fireEvent.mouseMove(window, { clientX: 550, clientY: 300 });

    // Stop drag
    fireEvent.mouseUp(window);

    await waitFor(() => {
      expect(api.setViewportConfig).toHaveBeenCalledWith(550, 300, 1.0, 0);
    });
  });

  it('scales from bottom when dragging top handle', async () => {
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

    // Drag Top handle downwards (current Y is 0)
    // Current Bottom is at Y = 500.
    // If we drag to Y = 250, new height is 500 - 250 = 250.
    // New Zoom = 500 / 250 = 2.0.
    // New Center Y = 500 - 250 / 2 = 375.
    fireEvent.mouseMove(window, { clientX: 500, clientY: 250 });

    // Stop drag
    fireEvent.mouseUp(window);

    await waitFor(() => {
      expect(api.setViewportConfig).toHaveBeenCalledWith(500, 375, 2.0, 0);
    });
  });

  it('scales from top when dragging bottom handle', async () => {
    const { container } = render(
      <CalibrationProvider>
        <EnableViewportEdit>
          <svg>
            <ViewportEditLayer />
          </svg>
        </EnableViewportEdit>
      </CalibrationProvider>
    );

    // Bottom handle is circles[3]
    const bottomHandle = container.querySelectorAll('circle')[3];

    // Start drag
    fireEvent.mouseDown(bottomHandle);

    // Drag Bottom handle upwards (current Y is 500)
    // Current Top is at Y = 0.
    // If we drag to Y = 250, new height is 250 - 0 = 250.
    // New Zoom = 500 / 250 = 2.0.
    // New Center Y = 0 + 250 / 2 = 125.
    fireEvent.mouseMove(window, { clientX: 500, clientY: 250 });

    // Stop drag
    fireEvent.mouseUp(window);

    await waitFor(() => {
      expect(api.setViewportConfig).toHaveBeenCalledWith(500, 125, 2.0, 0);
    });
  });
});
