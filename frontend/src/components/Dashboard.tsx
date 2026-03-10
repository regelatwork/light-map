import { useState } from 'react';
import { useSystemState } from '../hooks/useSystemState';
import { SchematicCanvas } from './SchematicCanvas';
import { ConfigurationSidebar } from './ConfigurationSidebar';
import { MapLibrary } from './MapLibrary';
import { CalibrationWizard } from './CalibrationWizard';

type ActiveTab = 'schematic' | 'calibration';

export const Dashboard = () => {
  const { isConnected, world, tokens } = useSystemState();
  const [activeTab, setActiveTab] = useState<ActiveTab>('schematic');

  return (
    <div className="flex h-screen bg-gray-100 overflow-hidden">
      <aside className="w-64 bg-white shadow-md flex flex-col z-10">
        <div className="flex items-center justify-between border-b p-4">
          <span className="font-bold text-black">Light Map Control</span>
          <div
            title={isConnected ? 'Connected' : 'Disconnected'}
            className={`h-3 w-3 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`}
          />
        </div>

        <div className="p-4 border-b">
          <nav className="flex flex-col space-y-2">
            <button
              onClick={() => setActiveTab('schematic')}
              className={`text-left px-3 py-2 rounded-md transition-colors ${
                activeTab === 'schematic'
                  ? 'bg-blue-50 text-blue-700 font-medium'
                  : 'text-gray-600 hover:bg-gray-50'
              }`}
            >
              Schematic View
            </button>
            <button
              onClick={() => setActiveTab('calibration')}
              className={`text-left px-3 py-2 rounded-md transition-colors ${
                activeTab === 'calibration'
                  ? 'bg-blue-50 text-blue-700 font-medium'
                  : 'text-gray-600 hover:bg-gray-50'
              }`}
            >
              Calibration Wizards
            </button>
          </nav>
        </div>

        <nav className="p-4 text-black flex-1 overflow-y-auto">
          <div className="mb-6">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-2">
              System Status
            </h3>
            <div className="space-y-1">
              <p className="text-sm">
                <span className="text-gray-500">Scene:</span> {world.scene}
              </p>
              <p className="text-sm">
                <span className="text-gray-500">FPS:</span> {world.fps?.toFixed(1)}
              </p>
              <p className="text-sm">
                <span className="text-gray-500">Tokens:</span> {tokens.length}
              </p>
            </div>
          </div>
          <div className="mb-6">
            <MapLibrary />
          </div>
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-2">
              Menu
            </h3>
            <p className="text-sm italic text-gray-400">No active menu</p>
          </div>
        </nav>
      </aside>
      <main className="flex-1 p-6 flex flex-col min-h-0">
        {activeTab === 'schematic' ? (
          <>
            <h2 className="mb-4 text-xl font-semibold text-gray-800">Schematic View</h2>
            <div className="flex-1 min-h-0 bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
              <SchematicCanvas>
                {/* Layers will be added here */}
                <text
                  x="500"
                  y="375"
                  textAnchor="middle"
                  className="fill-gray-300 font-bold text-4xl pointer-events-none"
                >
                  [Interactive Canvas Active]
                </text>
              </SchematicCanvas>
            </div>
          </>
        ) : (
          <CalibrationWizard />
        )}
      </main>
      <ConfigurationSidebar />
    </div>
  );
};
