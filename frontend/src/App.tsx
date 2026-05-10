import { Dashboard } from './components/Dashboard';
import { SelectionProvider } from './components/SelectionContext';
import { CalibrationProvider } from './components/CalibrationContext';
import { PlayerApp } from './apps/PlayerDashboard/PlayerApp';

function App() {
  const isPlayerDashboard = window.location.pathname === '/player';

  if (isPlayerDashboard) {
    return <PlayerApp />;
  }

  return (
    <CalibrationProvider>
      <SelectionProvider>
        <Dashboard />
      </SelectionProvider>
    </CalibrationProvider>
  );
}

export default App;
