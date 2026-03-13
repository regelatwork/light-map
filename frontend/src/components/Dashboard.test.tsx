import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { Dashboard } from './Dashboard';
import { SystemStateProvider } from '../hooks/useSystemState';
import { SelectionProvider } from './SelectionContext';
import { GridEditProvider } from './GridEditContext';

describe('Dashboard', () => {
  it('renders the sidebar title correctly', () => {
    render(
      <SystemStateProvider>
        <GridEditProvider>
          <SelectionProvider>
            <Dashboard />
          </SelectionProvider>
        </GridEditProvider>
      </SystemStateProvider>
    );
    const title = screen.getByText(/Light Map Control/i);
    expect(title).toBeInTheDocument();
  });

  it('renders the schematic view', () => {
    render(
      <SystemStateProvider>
        <GridEditProvider>
          <SelectionProvider>
            <Dashboard />
          </SelectionProvider>
        </GridEditProvider>
      </SystemStateProvider>
    );
    const placeholder = screen.getByRole('heading', { name: /Schematic View/i });
    expect(placeholder).toBeInTheDocument();
  });
});
