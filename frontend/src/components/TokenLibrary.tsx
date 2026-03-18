import React, { useState } from 'react';
import { useSystemState } from '../hooks/useSystemState';
import { updateProfile, deleteProfile, updateToken } from '../services/api';
import { useSelection } from './SelectionContext';
import { SelectionType } from '../types/system';

export const TokenLibrary: React.FC = () => {
  const { config } = useSystemState();
  const { setSelection } = useSelection();
  const [editingProfile, setEditingProfile] = useState<{
    name: string;
    size: number;
    height_mm: number;
  } | null>(null);
  const [isAddingProfile, setIsAddingProfile] = useState(false);
  const [newProfileName, setNewProfileName] = useState('');

  const [newArucoId, setNewArucoId] = useState('');

  const handleSaveProfile = async () => {
    if (editingProfile) {
      try {
        await updateProfile(editingProfile.name, editingProfile.size, editingProfile.height_mm);
        setEditingProfile(null);
      } catch (err) {
        console.error(err);
      }
    }
  };

  const handleAddProfile = async () => {
    if (newProfileName) {
      try {
        await updateProfile(newProfileName, 1, 10.0);
        setNewProfileName('');
        setIsAddingProfile(false);
      } catch (err) {
        console.error(err);
      }
    }
  };

  const handleDeleteProfile = async (name: string) => {
    if (window.confirm(`Delete profile "${name}"? Tokens using it will fallback to defaults.`)) {
      try {
        await deleteProfile(name);
      } catch (err) {
        console.error(err);
      }
    }
  };

  const handleAddAruco = async () => {
    const idNum = parseInt(newArucoId);
    if (!isNaN(idNum)) {
      try {
        await updateToken(idNum, { name: `New Token ${idNum}`, is_map_override: false });
        setNewArucoId('');
        setSelection({ type: SelectionType.TOKEN, id: idNum });
      } catch (err) {
        console.error(err);
      }
    }
  };

  return (
    <div className="flex flex-col h-full space-y-6 overflow-y-auto pr-2">
      {/* Token Profiles Section */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-bold text-gray-800">Token Profiles</h3>
          {!isAddingProfile && (
            <button
              onClick={() => setIsAddingProfile(true)}
              className="px-2 py-1 text-xs font-bold bg-green-600 text-white rounded hover:bg-green-700 transition-colors uppercase"
            >
              Add Profile
            </button>
          )}
        </div>

        {isAddingProfile && (
          <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-md flex space-x-2">
            <input
              type="text"
              placeholder="Profile Name"
              value={newProfileName}
              onChange={(e) => setNewProfileName(e.target.value)}
              className="flex-1 px-2 py-1 text-sm border rounded bg-white text-black"
            />
            <button
              onClick={handleAddProfile}
              className="px-3 py-1 text-xs font-bold bg-green-600 text-white rounded"
            >
              Create
            </button>
            <button
              onClick={() => setIsAddingProfile(false)}
              className="px-3 py-1 text-xs font-bold bg-gray-400 text-white rounded"
            >
              Cancel
            </button>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Object.entries(config.token_profiles || {})
            .filter(([_, profile]) => profile !== null && typeof profile === 'object')
            .map(([name, profile]) => (
              <div
                key={name}
              className="p-4 bg-white border border-gray-200 rounded-lg shadow-sm hover:border-blue-300 transition-colors"
            >
              {editingProfile?.name === name ? (
                <div className="space-y-3">
                  <p className="font-bold text-blue-700 text-sm">{name}</p>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-[10px] uppercase text-gray-400 font-bold">
                        Size
                      </label>
                      <input
                        type="number"
                        value={editingProfile.size}
                        onChange={(e) =>
                          setEditingProfile({ ...editingProfile, size: Number(e.target.value) })
                        }
                        className="w-full px-2 py-1 text-sm border rounded bg-white text-black"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] uppercase text-gray-400 font-bold">
                        Height (mm)
                      </label>
                      <input
                        type="number"
                        value={editingProfile.height_mm}
                        onChange={(e) =>
                          setEditingProfile({
                            ...editingProfile,
                            height_mm: Number(e.target.value),
                          })
                        }
                        className="w-full px-2 py-1 text-sm border rounded bg-white text-black"
                      />
                    </div>
                  </div>
                  <div className="flex space-x-2 pt-1">
                    <button
                      onClick={handleSaveProfile}
                      className="flex-1 bg-blue-600 text-white text-[10px] font-bold py-1 rounded"
                    >
                      SAVE
                    </button>
                    <button
                      onClick={() => setEditingProfile(null)}
                      className="flex-1 bg-gray-200 text-gray-600 text-[10px] font-bold py-1 rounded"
                    >
                      CANCEL
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  <div className="flex justify-between items-start mb-2">
                    <h4 className="font-bold text-gray-800">{name}</h4>
                    <div className="flex space-x-1">
                      <button
                        onClick={() => setEditingProfile({ name, ...profile })}
                        className="p-1 text-gray-400 hover:text-blue-600"
                        title="Edit Profile"
                      >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                        </svg>
                      </button>
                      <button
                        onClick={() => handleDeleteProfile(name)}
                        className="p-1 text-gray-400 hover:text-red-600"
                        title="Delete Profile"
                      >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>
                  </div>
                  <div className="text-xs text-gray-500 space-y-1">
                    <p>Size: <span className="font-semibold text-gray-700">{profile.size}</span></p>
                    <p>Height: <span className="font-semibold text-gray-700">{profile.height_mm}mm</span></p>
                  </div>
                </>
              )}
            </div>
          ))}
        </div>
      </section>

      <hr className="border-gray-200" />

      {/* ArUco Defaults Section */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-bold text-gray-800">ArUco Token Registry</h3>
          <div className="flex space-x-2">
            <input
              type="number"
              placeholder="ID"
              value={newArucoId}
              onChange={(e) => setNewArucoId(e.target.value)}
              className="w-16 px-2 py-1 text-xs border rounded bg-white text-black"
            />
            <button
              onClick={handleAddAruco}
              className="px-2 py-1 text-xs font-bold bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors uppercase"
            >
              Register ID
            </button>
          </div>
        </div>

        <div className="bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2 text-left text-[10px] font-bold text-gray-500 uppercase">ID</th>
                <th className="px-4 py-2 text-left text-[10px] font-bold text-gray-500 uppercase">Name</th>
                <th className="px-4 py-2 text-left text-[10px] font-bold text-gray-500 uppercase">Type</th>
                <th className="px-4 py-2 text-left text-[10px] font-bold text-gray-500 uppercase">Profile</th>
                <th className="px-4 py-2 text-right text-[10px] font-bold text-gray-500 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 text-black">
              {Object.entries(config.aruco_defaults || {})
                .filter(([_, def]) => def !== null && typeof def === 'object')
                .sort((a, b) => Number(a[0]) - Number(b[0]))
                .map(([id, def]) => (
                  <tr key={id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-2 text-sm font-mono">{id}</td>
                  <td className="px-4 py-2 text-sm font-medium">{def.name}</td>
                  <td className="px-4 py-2">
                    <span className={`px-2 py-0.5 text-[10px] font-bold rounded ${
                      def.type === 'PC' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                    }`}>
                      {def.type}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-sm text-gray-500">{def.profile || 'Manual'}</td>
                  <td className="px-4 py-2 text-right">
                    <button
                      onClick={() => setSelection({ type: SelectionType.TOKEN, id: Number(id) })}
                      className="text-blue-600 hover:text-blue-800 text-xs font-bold uppercase"
                    >
                      Configure
                    </button>
                  </td>
                </tr>
              ))}
              {Object.keys(config.aruco_defaults || {}).length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-sm text-gray-400 italic">
                    No ArUco tokens registered yet. Register an ID above or configure a token from the Schematic view.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
};
