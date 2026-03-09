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
        <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500">
          Map Library
        </h3>
        <button
          onClick={fetchMaps}
          className="text-[10px] font-bold text-blue-600 hover:text-blue-800 uppercase"
        >
          Refresh
        </button>
      </div>

      {isLoading && <p className="text-sm text-gray-400 italic">Loading maps...</p>}
      {error && <p className="text-sm text-red-500 font-medium">{error}</p>}

      {!isLoading && !error && maps.length === 0 && (
        <p className="text-sm text-gray-400 italic">No maps found. Register some with --maps.</p>
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
  );
};
