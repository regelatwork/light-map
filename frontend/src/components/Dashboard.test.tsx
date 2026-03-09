import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { Dashboard } from './Dashboard';
import { SystemStateProvider } from '../hooks/useSystemState';

describe('Dashboard', () => {
  it('renders the sidebar title correctly', () => {
    render(
      <SystemStateProvider>
        <Dashboard />
      </SystemStateProvider>
    );
    const title = screen.getByText(/Light Map Control/i);
    expect(title).toBeInTheDocument();
  });

  it('renders the schematic view', () => {
    render(
      <SystemStateProvider>
        <Dashboard />
      </SystemStateProvider>
    );
    const placeholder = screen.getByText(/Schematic View/i);
    expect(placeholder).toBeInTheDocument();
  });
});
