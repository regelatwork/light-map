/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useContext, useState, type ReactNode } from 'react';

interface GridEditContextType {
  isGridEditMode: boolean;
  setIsGridEditMode: (enabled: boolean) => void;
}

const GridEditContext = createContext<GridEditContextType | null>(null);

export const GridEditProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [isGridEditMode, setIsGridEditMode] = useState(false);

  return (
    <GridEditContext.Provider value={{ isGridEditMode, setIsGridEditMode }}>
      {children}
    </GridEditContext.Provider>
  );
};

export const useGridEdit = () => {
  const context = useContext(GridEditContext);
  if (!context) {
    throw new Error('useGridEdit must be used within a GridEditProvider');
  }
  return context;
};
