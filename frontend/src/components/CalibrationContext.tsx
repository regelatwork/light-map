/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useContext, useState, type ReactNode } from 'react';

export enum CalibrationMode {
  NONE = 'NONE',
  GRID = 'GRID',
  VIEWPORT = 'VIEWPORT',
}

interface CalibrationContextType {
  activeMode: CalibrationMode;
  setMode: (mode: CalibrationMode) => void;
}

const CalibrationContext = createContext<CalibrationContextType | null>(null);

export const CalibrationProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [activeMode, setActiveMode] = useState<CalibrationMode>(CalibrationMode.NONE);

  const setMode = (mode: CalibrationMode) => {
    setActiveMode(mode);
  };

  return (
    <CalibrationContext.Provider value={{ activeMode, setMode }}>
      {children}
    </CalibrationContext.Provider>
  );
};

export const useCalibration = () => {
  const context = useContext(CalibrationContext);
  if (!context) {
    throw new Error('useCalibration must be used within a CalibrationProvider');
  }
  return context;
};
