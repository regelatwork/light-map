import { Dashboard } from './components/Dashboard';
import { SelectionProvider } from './components/SelectionContext';
import { CalibrationProvider } from './components/CalibrationContext';

function App() {
  return (
    <CalibrationProvider>
      <SelectionProvider>
        <Dashboard />
      </SelectionProvider>
    </CalibrationProvider>
  );
}

export default App;
