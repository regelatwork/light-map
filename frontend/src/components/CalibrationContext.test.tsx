import { render, screen, act } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { CalibrationProvider, useCalibration, CalibrationMode } from './CalibrationContext';

const TestComponent = () => {
  const { activeMode, setMode } = useCalibration();
  return (
    <div>
      <div data-testid="active-mode">{activeMode}</div>
      <button onClick={() => setMode(CalibrationMode.GRID)}>Set Grid</button>
      <button onClick={() => setMode(CalibrationMode.VIEWPORT)}>Set Viewport</button>
      <button onClick={() => setMode(CalibrationMode.NONE)}>Set None</button>
    </div>
  );
};

describe('CalibrationContext', () => {
  it('defaults to NONE mode', () => {
    render(
      <CalibrationProvider>
        <TestComponent />
      </CalibrationProvider>
    );
    expect(screen.getByTestId('active-mode').textContent).toBe(CalibrationMode.NONE);
  });

  it('toggles modes correctly', () => {
    render(
      <CalibrationProvider>
        <TestComponent />
      </CalibrationProvider>
    );

    act(() => {
      screen.getByText('Set Grid').click();
    });
    expect(screen.getByTestId('active-mode').textContent).toBe(CalibrationMode.GRID);

    act(() => {
      screen.getByText('Set Viewport').click();
    });
    expect(screen.getByTestId('active-mode').textContent).toBe(CalibrationMode.VIEWPORT);

    act(() => {
      screen.getByText('Set None').click();
    });
    expect(screen.getByTestId('active-mode').textContent).toBe(CalibrationMode.NONE);
  });
});
