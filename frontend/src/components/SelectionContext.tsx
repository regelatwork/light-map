/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState, useCallback } from 'react';
import type { ReactNode } from 'react';
import { SelectionType } from '../types/system';
import { injectAction } from '../services/api';

interface SelectionState {
  type: SelectionType;
  id: string | number | null;
}

interface SelectionContextType {
  selection: SelectionState;
  setSelection: (selection: SelectionState) => void;
}

const SelectionContext = createContext<SelectionContextType | undefined>(undefined);

export const SelectionProvider = ({ children }: { children: ReactNode }) => {
  const [selection, setInternalSelection] = useState<SelectionState>({
    type: SelectionType.NONE,
    id: null,
  });

  const setSelection = useCallback((newSelection: SelectionState) => {
    setInternalSelection(newSelection);
    // Sync to backend
    injectAction('SET_SELECTION', JSON.stringify({
        type: newSelection.type,
        id: newSelection.id
    })).catch(err => console.error('Failed to sync selection to backend:', err));
  }, []);

  return (
    <SelectionContext.Provider value={{ selection, setSelection }}>
      {children}
    </SelectionContext.Provider>
  );
};

export const useSelection = () => {
  const context = useContext(SelectionContext);
  if (!context) {
    throw new Error('useSelection must be used within a SelectionProvider');
  }
  return context;
};
