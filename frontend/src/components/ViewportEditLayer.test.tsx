import { render, fireEvent, waitFor, cleanup } from '@testing-library/react';
import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
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
const mockUseSystemState = vi.fn();
vi.mock('../hooks/useSystemState', () => ({
  useSystemState: () => mockUseSystemState(),
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

  afterEach(() => {
    cleanup();
  });

  it('renders viewport rectangle and handles at correct world positions', () => {
    mockUseSystemState.mockReturnValue({
      isConnected: true,
      grid_spacing_svg: 50,
      config: {
        proj_res: [1000, 500],
      },
      world: {
        viewport: { x: 500, y: 250, zoom: 1.0, rotation: 0 },
      },
    });

    const { container } = render(
      <CalibrationProvider>
        <EnableViewportEdit>
          <svg>
            <ViewportEditLayer />
          </svg>
        </EnableViewportEdit>
      </CalibrationProvider>
    );

    const polygon = container.querySelector('polygon');
    expect(polygon).toBeInTheDocument();
    expect(polygon).toHaveAttribute('points', '-500,-250 500,-250 500,250 -500,250');

    const circles = container.querySelectorAll('circle');
    expect(circles[0]).toHaveAttribute('cx', '0');
    expect(circles[0]).toHaveAttribute('cy', '0');
  });

  it('calculates correct points with 90 degree rotation', () => {
    mockUseSystemState.mockReturnValue({
      isConnected: true,
      grid_spacing_svg: 50,
      config: {
        proj_res: [1000, 500],
      },
      world: {
        viewport: { x: 500, y: 250, zoom: 1.0, rotation: 90 },
      },
    });

    const { container } = render(
      <CalibrationProvider>
        <EnableViewportEdit>
          <svg>
            <ViewportEditLayer />
          </svg>
        </EnableViewportEdit>
      </CalibrationProvider>
    );

    const polygon = container.querySelector('polygon');
    expect(polygon).toBeInTheDocument();
    
    expect(polygon).toHaveAttribute('points', '-5.684341886080802e-14,1250 0,249.99999999999997 500,250 499.99999999999994,1250');

    const circles = container.querySelectorAll('circle');
    expect(circles[0]).toHaveAttribute('cx', '249.99999999999997');
    expect(circles[0]).toHaveAttribute('cy', '750');
  });

  it('calculates new translation when panning', async () => {
    mockUseSystemState.mockReturnValue({
      isConnected: true,
      grid_spacing_svg: 50,
      config: {
        proj_res: [1000, 500],
      },
      world: {
        viewport: { x: 500, y: 250, zoom: 1.0, rotation: 0 },
      },
    });

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
    fireEvent.mouseDown(centerHandle);
    fireEvent.mouseMove(window, { clientX: 100, clientY: 50 });
    fireEvent.mouseUp(window);

    await waitFor(() => {
      expect(api.setViewportConfig).toHaveBeenCalledWith(400, 200, 1.0, 0);
    });
  });

  it('calculates new zoom with 0 rotation', async () => {
    mockUseSystemState.mockReturnValue({
      isConnected: true,
      grid_spacing_svg: 50,
      config: {
        proj_res: [1000, 500],
      },
      world: {
        viewport: { x: 500, y: 250, zoom: 1.0, rotation: 0 },
      },
    });

    const { container } = render(
      <CalibrationProvider>
        <EnableViewportEdit>
          <svg>
            <ViewportEditLayer />
          </svg>
        </EnableViewportEdit>
      </CalibrationProvider>
    );

    const topHandle = container.querySelectorAll('circle')[2];
    fireEvent.mouseDown(topHandle);
    
    // As calculated in previous run
    fireEvent.mouseMove(window, { clientX: 500, clientY: 400 });
    fireEvent.mouseUp(window);

    await waitFor(() => {
      expect(api.setViewportConfig).toHaveBeenCalledWith(500, -333.33333333333337, 3.3333333333333335, 0);
    });
  });
});
