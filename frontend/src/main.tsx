import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import App from './App.tsx';
import { SystemStateProvider } from './hooks/useSystemState';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <SystemStateProvider>
      <App />
    </SystemStateProvider>
  </StrictMode>
);
