import React from 'react';

interface Target {
  id: string;
  name: string;
  ac_bonus: number;
  reflex_bonus: number;
  reason: string;
}

interface TacticalListProps {
  targets: Target[];
  onPing: (id: string) => void;
}

export const TacticalList: React.FC<TacticalListProps> = ({ targets, onPing }) => {
  return (
    <div className="space-y-3">
      {targets.map((target) => (
        <div 
          key={target.id}
          className="bg-slate-800 border border-slate-700 rounded-xl overflow-hidden shadow-md"
        >
          <div className="p-4 flex items-center justify-between gap-4">
            <div className="flex-1 min-w-0">
              <h3 className="font-bold text-lg truncate text-slate-100">{target.name}</h3>
              <div className="flex gap-3 mt-1">
                <span className={`text-xs px-2 py-0.5 rounded font-mono ${target.ac_bonus > 0 ? 'bg-amber-900/40 text-amber-400 border border-amber-800/50' : 'bg-slate-700 text-slate-400'}`}>
                  AC +{target.ac_bonus}
                </span>
                <span className={`text-xs px-2 py-0.5 rounded font-mono ${target.reflex_bonus > 0 ? 'bg-emerald-900/40 text-emerald-400 border border-emerald-800/50' : 'bg-slate-700 text-slate-400'}`}>
                  REF +{target.reflex_bonus}
                </span>
              </div>
            </div>
            
            <button
              onClick={() => onPing(target.id)}
              className="bg-slate-700 hover:bg-cyan-900 hover:text-cyan-400 p-3 rounded-lg border border-slate-600 hover:border-cyan-700 transition-all active:scale-90"
              title="Ping on Tabletop"
            >
              <span className="text-xl">📍</span>
            </button>
          </div>
          
          {target.reason && (
            <div className="bg-slate-900/50 px-4 py-2 border-t border-slate-700/50 flex items-center gap-2">
              <span className="text-[10px] text-slate-500 font-bold uppercase tracking-tight">Source:</span>
              <span className="text-xs text-slate-300 italic truncate">{target.reason}</span>
            </div>
          )}
        </div>
      ))}
    </div>
  );
};
