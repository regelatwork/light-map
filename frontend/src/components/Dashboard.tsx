import { useState } from 'react';
import { useSystemState } from '../hooks/useSystemState';
import { SchematicCanvas } from './SchematicCanvas';
import { ConfigurationSidebar } from './ConfigurationSidebar';
import { MapLibrary } from './MapLibrary';
import { CalibrationWizard } from './CalibrationWizard';
import { TokenLibrary } from './TokenLibrary';
import { SettingsModal } from './SettingsModal';
import { injectAction, interactMenu } from '../services/api';

type ActiveTab = 'schematic' | 'calibration' | 'library';

export const Dashboard = () => {
  const { isConnected, world, tokens, menu } = useSystemState();
  const [activeTab, setActiveTab] = useState<ActiveTab>('schematic');
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);

  const handleSummonMenu = async () => {
    try {
      await injectAction('TRIGGER_MENU');
    } catch (err) {
      console.error('Failed to summon menu:', err);
    }
  };

  const handleInteractMenu = async (index: number) => {
    try {
      await interactMenu(index);
    } catch (err) {
      console.error('Failed to interact with menu:', err);
    }
  };

  return (
    <div className="flex h-screen bg-gray-100 overflow-hidden">
      <SettingsModal isOpen={isSettingsOpen} onClose={() => setIsSettingsOpen(false)} />
      
      <aside className="w-64 bg-white shadow-md flex flex-col z-10">
        <div className="flex items-center justify-between border-b p-4">
          <span className="font-bold text-black">Light Map Control</span>
          <div className="flex items-center gap-2">
             <button 
              onClick={() => setIsSettingsOpen(true)}
              className="p-1 hover:bg-gray-100 rounded-lg transition-colors text-gray-500 hover:text-blue-600"
              title="System Settings"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            </button>
            <div
              title={isConnected ? 'Connected' : 'Disconnected'}
              className={`h-3 w-3 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`}
            />
          </div>
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
            <button
              onClick={() => setActiveTab('library')}
              className={`text-left px-3 py-2 rounded-md transition-colors ${
                activeTab === 'library'
                  ? 'bg-blue-50 text-blue-700 font-medium'
                  : 'text-gray-600 hover:bg-gray-50'
              }`}
            >
              Token Library
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
                <span className="text-gray-500">Scene:</span> {world?.scene || 'Unknown'}
              </p>
              <p className="text-sm">
                <span className="text-gray-500">FPS:</span>{' '}
                {typeof world?.fps === 'number' ? world.fps.toFixed(1) : '0.0'}
              </p>
              <p className="text-sm">
                <span className="text-gray-500">Tokens:</span> {tokens?.length || 0}
              </p>
            </div>
          </div>
          <div className="mb-6">
            <MapLibrary />
          </div>
          <div>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-500">Menu</h3>
              <button
                onClick={handleSummonMenu}
                className="px-2 py-0.5 text-[10px] font-bold bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors uppercase"
              >
                Summon
              </button>
            </div>
            {menu && menu.title && Array.isArray(menu.items) ? (
              <div className="space-y-1">
                <p className="text-sm font-medium text-blue-600">{menu.title}</p>
                <ul className="text-xs space-y-1 pl-2 border-l border-gray-100 max-h-48 overflow-y-auto">
                  {menu.items.map((item, idx) => (
                    <li
                      key={idx}
                      onClick={() => handleInteractMenu(idx)}
                      className="text-gray-700 truncate cursor-pointer hover:bg-blue-50 hover:text-blue-700 px-1 rounded transition-colors"
                      title={item}
                    >
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <p className="text-sm italic text-gray-400">No active menu</p>
            )}
          </div>
        </nav>
      </aside>
      <main className="flex-1 p-6 flex flex-col min-h-0">
        {activeTab === 'schematic' ? (
          <>
            <h2 className="mb-4 text-xl font-semibold text-gray-800">Schematic View</h2>
            <div className="flex-1 min-h-0 bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
              <SchematicCanvas>{/* Layers will be added here */}</SchematicCanvas>
            </div>
          </>
        ) : activeTab === 'calibration' ? (
          <CalibrationWizard />
        ) : (
          <>
            <h2 className="mb-4 text-xl font-semibold text-gray-800">Token Library</h2>
            <div className="flex-1 min-h-0">
              <TokenLibrary />
            </div>
          </>
        )}
      </main>
      <ConfigurationSidebar />
    </div>
  );
};
