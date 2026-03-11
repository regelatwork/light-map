# Real-time State Sync Hook Implementation Plan

> **For Gemini:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a React Context and Hook that maintains a persistent WebSocket connection to the backend and provides the system's live state to any component.

**Architecture:** A `SystemStateProvider` using `React.createContext` and `useReducer` to manage the live state. This ensures a single WebSocket connection for the entire application.

**Tech Stack:** React (TypeScript), WebSocket API.

______________________________________________________________________

### Task 1: Define System State Types & Initial State

**Files:**

- Create: `frontend/src/types/system.ts`

**Step 1: Define the TypeScript interfaces**
Create `frontend/src/types/system.ts` matching the backend broadcast structure.

```typescript
export interface WorldState {
  scene: string;
  fps: number;
  [key: string]: any;
}

export interface Token {
  id: number;
  world_x: number;
  world_y: number;
  [key: string]: any;
}

export interface SystemState {
  world: WorldState;
  tokens: Token[];
  menu: any;
  timestamp: number;
  isConnected: boolean;
  error: string | null;
}

export const INITIAL_STATE: SystemState = {
  world: { scene: 'LOADING', fps: 0 },
  tokens: [],
  menu: {},
  timestamp: 0,
  isConnected: false,
  error: null,
};
```

**Step 2: Commit**
Run: `git add frontend/src/types && git commit -m "feat(frontend): define system state types and initial state"`

______________________________________________________________________

### Task 2: Implement WebSocket URL Utility & SystemStateProvider

**Files:**

- Create: `frontend/src/hooks/useSystemState.tsx`

**Step 1: Implement WebSocket URL resolution**
Add logic to determine the WS URL:

```typescript
const getWsUrl = () => {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = import.meta.env.DEV ? 'localhost:8000' : window.location.host;
  return `${protocol}//${host}/ws/state`;
};
```

**Step 2: Create the Context and Provider**
Implement `SystemStateProvider` with:

- `useReducer` for state management.
- `useEffect` for WebSocket lifecycle.
- **Reconnection Logic**: Use `setTimeout` with a fixed interval (e.g., 3s) if the socket closes.
- **Error Handling**: Update state with `error` messages.

**Step 3: Create the `useSystemState` hook**
Export a simple hook to consume the context.

**Step 4: Commit**
Run: `git add frontend/src/hooks && git commit -m "feat(frontend): implement system state context provider and hook with reconnection logic"`

______________________________________________________________________

### Task 3: Integration and Visual Feedback (TDD)

**Files:**

- Modify: `frontend/src/main.tsx`
- Modify: `frontend/src/components/Dashboard.tsx`
- Create: `frontend/src/hooks/useSystemState.test.tsx`

**Step 1: Wrap App with Provider**
Modify `frontend/src/main.tsx` to include `<SystemStateProvider>`.

**Step 2: Update Dashboard with visual indicators**
Modify `Dashboard.tsx` to:

- Show a status dot (green/red) based on `isConnected`.
- Display live `world.scene` and `world.fps` in the sidebar or header.

**Step 3: Write tests (TDD)**
Create `frontend/src/hooks/useSystemState.test.tsx` using `vitest-websocket-mock` (or similar) to verify:

1. Initial state is correct.
1. `isConnected` becomes `true` on connection.
1. State updates correctly when JSON is received.
1. `isConnected` becomes `false` on disconnect.

**Step 4: Commit**
Run: `git add frontend && git commit -m "feat(frontend): integrate live state sync and visual status indicators"`
