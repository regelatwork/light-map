import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { Dashboard } from './Dashboard';

describe('Dashboard', () => {
  it('renders the sidebar title correctly', () => {
    render(<Dashboard />);
    const title = screen.getByText(/Light Map Control/i);
    expect(title).toBeInTheDocument();
  });

  it('renders the schematic view placeholder', () => {
    render(<Dashboard />);
    const placeholder = screen.getByText(/Schematic View Placeholder/i);
    expect(placeholder).toBeInTheDocument();
  });
});
