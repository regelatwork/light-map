import { Dashboard } from './components/Dashboard';
import { SelectionProvider } from './components/SelectionContext';

function App() {
  return (
    <SelectionProvider>
      <Dashboard />
    </SelectionProvider>
  );
}

export default App;
