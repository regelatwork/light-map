import React, { useState, useEffect } from 'react';
import { CharacterSelector } from './CharacterSelector';
import { TacticalList } from './TacticalList';
import { API_BASE_URL, WS_URL } from '../../services/config';

interface TacticalTarget {
  id: number;
  name: string;
  ac_bonus: number;
  reflex_bonus: number;
  reason: string;
}

interface TacticalState {
  attacker_id: string | null;
  is_exclusive_active: boolean;
  targets: TacticalTarget[];
}

export const PlayerApp: React.FC = () => {
  const [selectedTokenId, setSelectedTokenId] = useState<string | null>(
    localStorage.getItem('player_selected_token_id')
  );
  const [tacticalState, setTacticalState] = useState<TacticalState | null>(null);

  useEffect(() => {
    // Basic polling or WebSocket connection would go here
    // For now, let's assume we have a global state mirror or similar service
    const ws = new WebSocket(WS_URL);

    ws.onmessage = (event) => {
      const state = JSON.parse(event.data);
      if (state.world?.tactical) {
        setTacticalState(state.world.tactical);
      }
    };

    return () => ws.close();
  }, []);

  const handleSelectCharacter = (id: string) => {
    setSelectedTokenId(id);
    localStorage.setItem('player_selected_token_id', id);
  };

  const toggleVision = async () => {
    const isCurrentlyActive =
      tacticalState?.is_exclusive_active && tacticalState?.attacker_id === selectedTokenId;

    await fetch(`${API_BASE_URL}/actions/exclusive-vision`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token_id: isCurrentlyActive ? null : selectedTokenId }),
    });
  };

  const triggerPing = async (targetId: string) => {
    await fetch(`${API_BASE_URL}/actions/ping`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token_id: targetId }),
    });
  };

  if (!selectedTokenId) {
    return <CharacterSelector onSelect={handleSelectCharacter} />;
  }

  const isVisionActive =
    tacticalState?.is_exclusive_active && tacticalState?.attacker_id === selectedTokenId;

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 p-4 font-sans select-none">
      <header className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-xl font-bold text-cyan-400">Tactical Dashboard</h1>
          <p className="text-sm text-slate-400">Token ID: {selectedTokenId}</p>
        </div>
        <button
          onClick={() => {
            setSelectedTokenId(null);
            localStorage.removeItem('player_selected_token_id');
          }}
          className="text-xs bg-slate-800 hover:bg-slate-700 px-3 py-1 rounded border border-slate-700 transition-colors"
        >
          Switch Hero
        </button>
      </header>

      <div className="mb-8">
        <button
          onClick={toggleVision}
          className={`w-full py-6 rounded-xl font-bold text-lg shadow-lg transition-all active:scale-95 flex flex-col items-center justify-center gap-2 border-2 ${
            isVisionActive
              ? 'bg-cyan-500 border-cyan-400 text-white shadow-cyan-900/40'
              : 'bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-750'
          }`}
        >
          <span className="text-3xl">{isVisionActive ? '👁️' : '🕶️'}</span>
          {isVisionActive ? 'EXCLUSIVE VISION ACTIVE' : 'ENABLE EXCLUSIVE VISION'}
        </button>
        <p className="text-center text-xs text-slate-500 mt-2 italic">
          Toggle this when it is your turn to see through your character's eyes on the map.
        </p>
      </div>

      <section>
        <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4 px-1">
          Visible Targets
        </h2>
        {tacticalState?.targets && tacticalState.targets.length > 0 ? (
          <TacticalList
            targets={tacticalState.targets.map((t) => ({ ...t, id: String(t.id) }))}
            onPing={triggerPing}
          />
        ) : (
          <div className="bg-slate-800/50 border border-slate-700 rounded-lg p-8 text-center text-slate-500 italic">
            No enemies currently in sight.
          </div>
        )}
      </section>

      <footer className="mt-12 text-center text-[10px] text-slate-600 uppercase tracking-[0.2em]">
        Light Map Tactical Engine • v1.0
      </footer>
    </div>
  );
};
