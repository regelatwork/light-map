import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { Dashboard } from './Dashboard';
import { SystemStateProvider } from '../hooks/useSystemState';
import { SelectionProvider } from './SelectionContext';

describe('Dashboard', () => {
  it('renders the sidebar title correctly', () => {
    render(
      <SystemStateProvider>
        <SelectionProvider>
          <Dashboard />
        </SelectionProvider>
      </SystemStateProvider>
    );
    const title = screen.getByText(/Light Map Control/i);
    expect(title).toBeInTheDocument();
  });

  it('renders the schematic view', () => {
    render(
      <SystemStateProvider>
        <SelectionProvider>
          <Dashboard />
        </SelectionProvider>
      </SystemStateProvider>
    );
    const placeholder = screen.getByText(/Schematic View/i);
    expect(placeholder).toBeInTheDocument();
  });
});
