# Frontend Testing Framework Implementation Plan

> **For Gemini:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Integrate Vitest and React Testing Library for the frontend, following a TDD workflow for the first test.

**Architecture:** A lightweight unit-testing setup focused on component behavior.

**Tech Stack:** Vitest, React Testing Library, `jsdom`, `@vitejs/plugin-react`.

______________________________________________________________________

### Task 1: Install Testing Dependencies

**Files:**

- Modify: `frontend/package.json`

**Step 1: Install dependencies**
Run: `cd frontend && npm install -D vitest @testing-library/react @testing-library/jest-dom @testing-library/user-event @vitejs/plugin-react jsdom --silent`
Expected: `package.json` updated.

**Step 2: Commit**
Run: `git add frontend/package.json && git commit -m "chore(frontend): install vitest and react testing library"`

______________________________________________________________________

### Task 2: Configure Vitest

**Files:**

- Create: `frontend/vitest.config.ts`
- Create: `frontend/src/test/setup.ts`

**Step 1: Create Vitest configuration**
Create: `frontend/vitest.config.ts`

```typescript
import { defineConfig, mergeConfig } from 'vitest/config';
import viteConfig from './vite.config';

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      globals: true,
      environment: 'jsdom',
      setupFiles: './src/test/setup.ts',
      css: true,
    },
  })
);
```

**Step 2: Create test setup file**
Create: `frontend/src/test/setup.ts`

```typescript
import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

// Automatically cleanup after each test
afterEach(() => {
  cleanup();
});
```

**Step 3: Update `package.json` with test script**
Modify: `frontend/package.json`

```json
"scripts": {
  "test": "vitest run",
  "test:watch": "vitest",
  ...
}
```

**Step 4: Commit**
Run: `git add frontend && git commit -m "chore(frontend): configure vitest and setup tests"`

______________________________________________________________________

### Task 3: Implement Initial Dashboard Test (TDD)

**Files:**

- Create: `frontend/src/components/Dashboard.test.tsx`

**Step 1: Write failing test**
Create: `frontend/src/components/Dashboard.test.tsx`

```tsx
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { Dashboard } from './Dashboard';

describe('Dashboard', () => {
  it('renders the sidebar title correctly', () => {
    render(<Dashboard />);
    const title = screen.getByText(/Light Map Control/i);
    expect(title).toBeInTheDocument();
  });

  it('renders the schematic view placeholder', () => {
    render(<Dashboard />);
    const placeholder = screen.getByText(/Schematic View Placeholder/i);
    expect(placeholder).toBeInTheDocument();
  });
});
```

**Step 2: Run test and verify it passes**
Run: `cd frontend && npm run test`
Expected: 2 tests passed.

**Step 3: Final check and Commit**
Run: `git add frontend && git commit -m "test(frontend): add initial dashboard component tests"`
