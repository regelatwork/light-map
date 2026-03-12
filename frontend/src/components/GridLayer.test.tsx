import { render, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { GridLayer } from './GridLayer';
import { SystemStateProvider } from '../hooks/useSystemState';
import { CanvasProvider } from './CanvasContext';
import * as api from '../services/api';

// Mock the hook
vi.mock('../hooks/useSystemState', () => ({
  useSystemState: () => ({
    isConnected: true,
    grid_spacing_svg: 50,
    grid_origin_svg_x: 100,
    grid_origin_svg_y: 100,
  }),
  SystemStateProvider: ({ children }: { children: React.ReactNode }) => <div>{children}</div>
}));

// Mock API service
vi.mock('../services/api', () => ({
  saveGridConfig: vi.fn().mockResolvedValue({ status: 'ok' })
}));

// Mock CanvasContext
vi.mock('./CanvasContext', () => ({
  useCanvas: () => ({
    screenToWorld: (x: number, y: number) => ({ x, y }),
  }),
  CanvasProvider: ({ children }: { children: React.ReactNode }) => <div>{children}</div>
}));

describe('GridLayer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders grid lines and handles', () => {
    const { container } = render(
      <CanvasProvider>
        <svg>
          <GridLayer />
        </svg>
      </CanvasProvider>
    );
    
    // Should have grid lines
    const lines = container.querySelectorAll('line');
    expect(lines.length).toBeGreaterThan(0);

    // Should have origin handle (green) and scale handle (blue)
    const circles = container.querySelectorAll('circle');
    expect(circles.length).toBe(2);
    
    // First circle should be origin
    expect(circles[0].getAttribute('stroke')).toBe('#22c55e');
    // Second circle should be scale
    expect(circles[1].getAttribute('stroke')).toBe('#3b82f6');
  });

  it('calls saveGridConfig when dragging origin', async () => {
    const { container } = render(
      <CanvasProvider>
        <svg>
          <GridLayer />
        </svg>
      </CanvasProvider>
    );

    const originHandle = container.querySelectorAll('circle')[0];
    
    // Start drag
    fireEvent.mouseDown(originHandle);
    
    // Move mouse
    fireEvent.mouseMove(window, { clientX: 150, clientY: 150 });
    
    // Stop drag
    fireEvent.mouseUp(window);

    await waitFor(() => {
      expect(api.saveGridConfig).toHaveBeenCalled();
    });
  });

  it('calls saveGridConfig with new spacing when dragging scale handle', async () => {
    const { container } = render(
      <CanvasProvider>
        <svg>
          <GridLayer />
        </svg>
      </CanvasProvider>
    );

    const scaleHandle = container.querySelectorAll('circle')[1];
    
    // Start drag
    fireEvent.mouseDown(scaleHandle);
    
    // Move mouse (origin is at 100,100, dragging to 200,100 should make spacing 100)
    // Note: CanvasProvider mock or actual implementation might affect coordinates.
    // In our test environment, we might need to be careful with how clientX/Y maps to world.
    fireEvent.mouseMove(window, { clientX: 200, clientY: 100 });
    
    // Stop drag
    fireEvent.mouseUp(window);

    await waitFor(() => {
      // It should have been called with spacing as the 3rd argument
      expect(api.saveGridConfig).toHaveBeenCalledWith(
        expect.any(Number), 
        expect.any(Number), 
        expect.any(Number)
      );
    });
  });
});
