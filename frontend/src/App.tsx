import { Dashboard } from './components/Dashboard';
import { SelectionProvider } from './components/SelectionContext';
import { GridEditProvider } from './components/GridEditContext';

function App() {
  return (
    <GridEditProvider>
      <SelectionProvider>
        <Dashboard />
      </SelectionProvider>
    </GridEditProvider>
  );
}

export default App;
