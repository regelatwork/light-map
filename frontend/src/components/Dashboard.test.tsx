import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { Dashboard } from './Dashboard';
import { SystemStateProvider } from '../hooks/useSystemState';
import { SelectionProvider } from './SelectionContext';
import { CalibrationProvider } from './CalibrationContext';

describe('Dashboard', () => {
  it('renders the sidebar title correctly', () => {
    render(
      <SystemStateProvider>
        <CalibrationProvider>
          <SelectionProvider>
            <Dashboard />
          </SelectionProvider>
        </CalibrationProvider>
      </SystemStateProvider>
    );
    const title = screen.getByText(/Light Map Control/i);
    expect(title).toBeInTheDocument();
  });

  it('renders the schematic view', () => {
    render(
      <SystemStateProvider>
        <CalibrationProvider>
          <SelectionProvider>
            <Dashboard />
          </SelectionProvider>
        </CalibrationProvider>
      </SystemStateProvider>
    );
    const placeholder = screen.getByRole('heading', { name: /Schematic View/i });
    expect(placeholder).toBeInTheDocument();
  });
});
