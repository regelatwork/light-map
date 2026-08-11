import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { TacticalList } from './TacticalList';

describe('TacticalList', () => {
  it('renders a list of targets', () => {
    const mockTargets = [
      { id: '1', name: 'Orc 1', ac_bonus: 2, reflex_bonus: 1, reason: 'Cover', type: 'NPC' },
      { id: '2', name: 'Hero', ac_bonus: 1, reflex_bonus: 2, reason: 'None', type: 'PC' },
    ];
    const mockOnPing = vi.fn();

    render(<TacticalList targets={mockTargets} onPing={mockOnPing} />);

    expect(screen.getByText('Orc 1')).toBeInTheDocument();
    expect(screen.getByText('Hero')).toBeInTheDocument();
  });

  it('sorts targets such that NPCs appear before PCs', () => {
    const mockTargets = [
      { id: '1', name: 'Hero', ac_bonus: 1, reflex_bonus: 2, reason: 'None', type: 'PC' },
      { id: '2', name: 'Orc 1', ac_bonus: 2, reflex_bonus: 1, reason: 'Cover', type: 'NPC' },
      { id: '3', name: 'Hero 2', ac_bonus: 1, reflex_bonus: 2, reason: 'None', type: 'PC' },
      { id: '4', name: 'Orc 2', ac_bonus: 2, reflex_bonus: 1, reason: 'Cover', type: 'NPC' },
    ];
    const mockOnPing = vi.fn();

    render(<TacticalList targets={mockTargets} onPing={mockOnPing} />);

    const listItems = screen.getAllByRole('heading', { level: 3 });
    // Expected order: Orc 1, Orc 2, Hero, Hero 2
    expect(listItems[0]).toHaveTextContent('Orc 1');
    expect(listItems[1]).toHaveTextContent('Orc 2');
    expect(listItems[2]).toHaveTextContent('Hero');
    expect(listItems[3]).toHaveTextContent('Hero 2');
  });

  it('sorts targets alphabetically by name if they have the same type', () => {
    const mockTargets = [
      { id: '1', name: 'Hero 2', ac_bonus: 1, reflex_bonus: 2, reason: 'None', type: 'PC' },
      { id: '2', name: 'Hero 1', ac_bonus: 1, reflex_bonus: 2, reason: 'None', type: 'PC' },
    ];
    const mockOnPing = vi.fn();

    render(<TacticalList targets={mockTargets} onPing={mockOnPing} />);

    const listItems = screen.getAllByRole('heading', { level: 3 });
    expect(listItems[0]).toHaveTextContent('Hero 1');
    expect(listItems[1]).toHaveTextContent('Hero 2');
  });
});
