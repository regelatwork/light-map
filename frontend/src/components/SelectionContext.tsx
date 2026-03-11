/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState } from 'react';
import type { ReactNode } from 'react';
import { SelectionType } from '../types/system';

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
  const [selection, setSelection] = useState<SelectionState>({ type: SelectionType.NONE, id: null });
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
