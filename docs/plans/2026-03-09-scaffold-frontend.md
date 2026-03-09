# Scaffold React Application Implementation Plan

> **For Gemini:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Initialize a modern React frontend using Vite and Tailwind CSS in a dedicated `frontend/` directory, including linting, formatting, and proper git hygiene.

**Architecture:** A standalone Single-Page Application (SPA) that will be built into static assets for the FastAPI backend to serve.

**Tech Stack:** React (TypeScript), Vite, Tailwind CSS, PostCSS, Autoprefixer, ESLint, Prettier.

---

### Task 1: Scaffold React Project with Vite

**Files:**
- Create: `frontend/` (directory)
- Create: `frontend/package.json`, `frontend/vite.config.ts`, etc. (via `npm create vite`)

**Step 1: Create the project structure**
Run: `npm create vite@latest frontend -- --template react-ts --yes`
Expected: `frontend/` directory created with boilerplate.

**Step 2: Install initial dependencies**
Run: `cd frontend && npm install --silent`
Expected: `node_modules/` populated.

**Step 3: Verify the scaffold**
Run: `cd frontend && npm run build`
Expected: `dist/` directory created with index.html.

**Step 4: Commit**
Run: `git add frontend && git commit -m "feat(frontend): scaffold react-ts project with vite"`

---

### Task 2: Configure Tailwind CSS

**Files:**
- Create: `frontend/tailwind.config.js`
- Create: `frontend/postcss.config.js`
- Modify: `frontend/src/index.css`

**Step 1: Install Tailwind dependencies**
Run: `cd frontend && npm install -D tailwindcss postcss autoprefixer --silent`
Expected: `package.json` updated.

**Step 2: Initialize Tailwind configuration**
Run: `cd frontend && npx tailwindcss init -p`
Expected: `tailwind.config.js` and `postcss.config.js` created.

**Step 3: Configure Tailwind to scan source files**
Modify: `frontend/tailwind.config.js`
```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
```

**Step 4: Add Tailwind directives to CSS**
Modify: `frontend/src/index.css` (Replace content)
```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

**Step 5: Verify Tailwind is working**
Modify: `frontend/src/App.tsx`
```tsx
function App() {
  return (
    <div className="bg-blue-500 text-white p-4">
      <h1 className="text-2xl font-bold">Tailwind is Active</h1>
    </div>
  )
}
export default App
```
Run: `cd frontend && npm run build`
Expected: CSS in `dist/` includes Tailwind utility classes.

**Step 6: Commit**
Run: `git add frontend && git commit -m "feat(frontend): add tailwind css configuration"`

---

### Task 3: Linting, Formatting, and Git Hygiene

**Files:**
- Create: `frontend/.gitignore`
- Create: `frontend/.prettierrc`
- Create: `frontend/.prettierignore`
- Modify: `frontend/package.json`

**Step 1: Create frontend .gitignore**
Create: `frontend/.gitignore`
```text
# Logs
logs
*.log
npm-debug.log*
yarn-debug.log*
yarn-error.log*
pnpm-debug.log*
lerna-debug.log*

node_modules
dist
dist-ssr
*.local

# Editor directories and files
.vscode/*
!.vscode/extensions.json
.idea
.DS_Store
*.suo
*.ntvs*
*.njsproj
*.sln
*.sw?
```

**Step 2: Install Prettier and ESLint plugins**
Run: `cd frontend && npm install -D prettier eslint-plugin-prettier eslint-config-prettier --silent`
Expected: `package.json` updated.

**Step 3: Create Prettier configuration**
Create: `frontend/.prettierrc`
```json
{
  "semi": true,
  "tabWidth": 2,
  "printWidth": 100,
  "singleQuote": true,
  "trailingComma": "es5",
  "bracketSpacing": true
}
```

**Step 4: Create Prettier ignore file**
Create: `frontend/.prettierignore`
```text
node_modules
dist
package-lock.json
```

**Step 5: Add lint and format scripts**
Modify: `frontend/package.json` (Update `scripts` section)
```json
"scripts": {
  "dev": "vite",
  "build": "tsc && vite build",
  "lint": "eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0",
  "format": "prettier --write .",
  "preview": "vite preview"
},
```

**Step 6: Run formatter**
Run: `cd frontend && npm run format`
Expected: All files formatted.

**Step 7: Commit**
Run: `git add frontend && git commit -m "chore(frontend): add linting, formatting, and gitignore"`

---

### Task 4: Basic Layout & Directory Structure

**Files:**
- Create: `frontend/src/components/`, `frontend/src/hooks/`, `frontend/src/services/`
- Create: `frontend/src/components/Dashboard.tsx`
- Modify: `frontend/src/App.tsx`

**Step 1: Create component directories**
Run: `mkdir -p frontend/src/{components,hooks,services}`
Expected: Directories created.

**Step 2: Create a placeholder Dashboard component**
Create: `frontend/src/components/Dashboard.tsx`
```tsx
export const Dashboard = () => {
  return (
    <div className="flex h-screen bg-gray-100">
      <aside className="w-64 bg-white shadow-md">
        <div className="p-4 font-bold border-b text-black">Light Map Control</div>
        <nav className="p-4 text-black">Sidebar Content</nav>
      </aside>
      <main className="flex-1 p-8 overflow-auto">
        <h2 className="text-xl font-semibold mb-4 text-black text-black">Schematic View Placeholder</h2>
        <div className="bg-white border-2 border-dashed border-gray-300 h-96 flex items-center justify-center text-black">
          [Interactive Canvas Will Go Here]
        </div>
      </main>
    </div>
  );
};
```

**Step 3: Update App entry point**
Modify: `frontend/src/App.tsx`
```tsx
import { Dashboard } from './components/Dashboard';

function App() {
  return <Dashboard />;
}

export default App;
```

**Step 4: Final build and lint check**
Run: `cd frontend && npm run format && npm run build`
Expected: SUCCESS.

**Step 5: Commit**
Run: `git add frontend && git commit -m "feat(frontend): initial dashboard layout and directory structure"`
