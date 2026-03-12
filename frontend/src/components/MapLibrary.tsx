import React, { useState, useEffect } from 'react';
import { getMaps, loadMap } from '../services/api';

interface MapInfo {
  path: string;
  name: string;
}

export const MapLibrary: React.FC = () => {
  const [maps, setMaps] = useState<MapInfo[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isExpanded, setIsExpanded] = useState(true);

  const fetchMaps = async () => {
    setIsLoading(true);
    try {
      const data = await getMaps();
      setMaps(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to fetch maps');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchMaps();
  }, []);

  const handleLoadMap = async (path: string) => {
    try {
      await loadMap(path);
    } catch (e) {
      console.error(e);
      alert(e instanceof Error ? e.message : 'Failed to load map');
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="flex items-center space-x-2 group"
        >
          <svg
            className={`h-3 w-3 text-gray-400 group-hover:text-gray-600 transition-transform ${
              isExpanded ? 'rotate-0' : '-rotate-90'
            }`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 group-hover:text-gray-700">
            Map Library
          </h3>
        </button>
        {isExpanded && (
          <button
            onClick={fetchMaps}
            className="text-[10px] font-bold text-blue-600 hover:text-blue-800 uppercase"
          >
            Refresh
          </button>
        )}
      </div>

      {isExpanded && (
        <div className="space-y-4 animate-in fade-in slide-in-from-top-1 duration-200">
          {isLoading && <p className="text-sm text-gray-400 italic">Loading maps...</p>}
          {error && <p className="text-sm text-red-500 font-medium">{error}</p>}

          {!isLoading && !error && maps.length === 0 && (
            <p className="text-sm text-gray-400 italic">
              No maps found. Register some with --maps.
            </p>
          )}

          <ul className="space-y-1">
            {maps.map((map) => (
              <li key={map.path}>
                <button
                  onClick={() => handleLoadMap(map.path)}
                  className="w-full text-left px-3 py-2 text-sm rounded hover:bg-gray-100 text-gray-700 transition-colors truncate border border-transparent hover:border-gray-200 group"
                  title={map.path}
                >
                  <div className="font-medium group-hover:text-blue-600 truncate">{map.name}</div>
                  <div className="text-[10px] text-gray-400 truncate font-mono">{map.path}</div>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};
