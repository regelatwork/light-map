/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState } from 'react';
import type { ReactNode } from 'react';

type SelectionType = 'token' | 'none';

interface SelectionState {
  type: SelectionType;
  id: number | null;
}

interface SelectionContextType {
  selection: SelectionState;
  setSelection: (selection: SelectionState) => void;
}

const SelectionContext = createContext<SelectionContextType | undefined>(undefined);

export const SelectionProvider = ({ children }: { children: ReactNode }) => {
  const [selection, setSelection] = useState<SelectionState>({ type: 'none', id: null });
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
