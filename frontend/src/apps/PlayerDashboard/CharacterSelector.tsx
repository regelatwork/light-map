import React, { useState, useEffect } from 'react';
import { API_BASE_URL } from '../../services/config';
import type { ArucoDefinition } from '../../types/schema.generated';

interface CharacterSelectorProps {
  onSelect: (id: string) => void;
}

interface PCToken extends ArucoDefinition {
  id: string;
}

export const CharacterSelector: React.FC<CharacterSelectorProps> = ({ onSelect }) => {
  const [pcTokens, setPcTokens] = useState<PCToken[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchTokens = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/config`);
        const config = await response.json();
        const tokens = (config.aruco_defaults || {}) as Record<string, ArucoDefinition>;
        const pcs = Object.entries(tokens)
          .filter(([, t]) => t.type === 'PC')
          .map(([id, t]) => ({ id, ...t }))
          .sort((a, b) => {
            const nameA = a.name || `Token ${a.id}`;
            const nameB = b.name || `Token ${b.id}`;
            return nameA.localeCompare(nameB, undefined, { numeric: true });
          });

        setPcTokens(pcs);
      } catch (e) {
        console.error('Failed to fetch PC tokens, falling back to manual entry', e);
      } finally {
        setLoading(false);
      }
    };

    fetchTokens();
  }, []);

  const [manualId, setManualId] = useState('');

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 p-8 flex flex-col items-center justify-center">
      <div className="w-full max-w-md">
        <h1 className="text-3xl font-bold text-cyan-400 mb-2 text-center">Claim Your Hero</h1>
        <p className="text-slate-400 text-center mb-8">
          Select your character to access your tactical dashboard.
        </p>

        <div className="space-y-4">
          {pcTokens.map((pc) => (
            <button
              key={pc.id}
              onClick={() => onSelect(pc.id)}
              className="w-full bg-slate-800 hover:bg-slate-700 border border-slate-700 p-4 rounded-xl flex items-center gap-4 transition-all active:scale-[0.98]"
            >
              <div
                className="w-12 h-12 rounded-full border-2 flex items-center justify-center text-xl"
                style={{ borderColor: pc.color || '#22d3ee', color: pc.color || '#22d3ee' }}
              >
                {pc.name?.[0] || '?'}
              </div>
              <div className="text-left">
                <div className="font-bold text-lg">{pc.name || `Token ${pc.id}`}</div>
                <div className="text-xs text-slate-500 uppercase tracking-tight">ID: {pc.id}</div>
              </div>
              <div className="ml-auto text-cyan-500">→</div>
            </button>
          ))}

          {pcTokens.length === 0 && !loading && (
            <div className="bg-slate-800/50 border border-dashed border-slate-700 p-6 rounded-xl text-center">
              <p className="text-slate-500 text-sm mb-4">No PC tokens found in configuration.</p>
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="Enter Token ID (e.g. 42)"
                  value={manualId}
                  onChange={(e) => setManualId(e.target.value)}
                  className="flex-1 bg-slate-900 border border-slate-700 rounded px-3 py-2 text-sm focus:outline-none focus:border-cyan-500"
                />
                <button
                  onClick={() => manualId && onSelect(manualId)}
                  className="bg-cyan-600 hover:bg-cyan-500 px-4 py-2 rounded text-sm font-bold transition-colors"
                >
                  Join
                </button>
              </div>
            </div>
          )}

          {loading && (
            <div className="text-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-cyan-500 mx-auto"></div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
