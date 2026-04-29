# Plan: E2E Test Type Sweep (REVISED)

## Overview
Systematically remove `any` and `eslint-disable-next-line @typescript-eslint/no-explicit-any` from the Playwright E2E test suite. 

## Phase 1: Discovery & Analysis (Delegated)
We will map every `any` usage in the existing `frontend/e2e` directory.

### Chunk A: Core Spec Files
*   **Files:** `dashboard.spec.ts`, `map-centering.spec.ts`.
*   **Focus:** Window injection, configuration mocks, and layout assertions.

### Chunk B: Tactical & Real Integration
*   **Files:** `tactical_cover.spec.ts`, `tactical_real.spec.ts`.
*   **Focus:** WebSocket message payloads, `MockWebSocket` implementation, and API response parsing.

## Phase 2: Tooling & Utilities (The "Refactor" Step)
To make this easier for a junior engineer and more maintainable:
1.  **Sync Backend Types:** Run `python3 scripts/generate_ts_schema.py` to ensure `frontend/src/types/schema.generated.ts` is up-to-date.
2.  **Extract MockWebSocket:** Create `frontend/e2e/utils/mock-socket.ts`.
    *   Implement a properly typed `MockWebSocket` class.
    *   Avoid `any` in `onmessage` and `send` by using `unknown` and type guards or generics.
3.  **Define Shared E2E Types:** Create `frontend/e2e/types/e2e.ts` for interfaces like `E2EWindow` (extending `Window` to include `VITE_API_HOST`).

## Phase 3: Implementation Guide (Junior-Ready)
Follow these patterns for each fix:

### 1. Global Window Injection
**Before:** `(window as any).VITE_API_HOST = host;`
**After:** 
```typescript
import { E2EWindow } from './types/e2e';
(window as unknown as E2EWindow).VITE_API_HOST = host;
```

### 2. WebSocket Messages
**Before:** `onmessage: (msg: any) => void;`
**After:** 
```typescript
import { SystemState } from '../src/types/system';
// ... in MockWebSocket
onmessage: (event: { data: string }) => void;
// ... when receiving
const data = JSON.parse(event.data) as SystemState;
```

### 3. API Response Data
**Before:** `let data: any = {};`
**After:** 
```typescript
import { TacticalCoverResponse } from '../src/types/schema.generated';
let data: Partial<TacticalCoverResponse> = {};
```

## Phase 4: Verification
1.  **Lint:** `npm run lint` in `frontend/`.
2.  **Type-check:** `npm run build` (runs `tsc`).
3.  **Execution:** `npx playwright test`.

## Expected Deliverables
*   `frontend/e2e/utils/mock-socket.ts` (Refactored shared utility).
*   `frontend/e2e/types/e2e.ts` (Shared interfaces).
*   Zero `any` usages in `frontend/e2e/*.spec.ts`.
