# Center on Grid Origin with Map Center Fallback Implementation Plan

> **For Gemini:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Correctly center the map on the grid origin (accounting for rotation) or fallback to the map center if no origin is set. Fix the trigger logic to prevent premature centering before map data is available.

**Architecture:**

1. Update `resetView` in `SchematicCanvas.tsx` to include a fallback mechanism: Grid Origin -> Map Center -> Projection Center.
1. Replace the boolean `initialCentered` ref with a more specific `lastCenteredMapPath` ref to trigger centering only when a map is actually loaded.
1. Verify with the existing Playwright E2E test `frontend/e2e/map-centering.spec.ts`.

**Tech Stack:** React (TypeScript), Playwright.

______________________________________________________________________

### Task 1: Update `resetView` and trigger logic in `SchematicCanvas.tsx`

**Files:**

- Modify: `frontend/src/components/SchematicCanvas.tsx`

**Step 1: Implement fallback and better trigger logic**

Replace the existing `resetView` and `useLayoutEffect` blocks.

```typescript
  const lastCenteredMapPath = useRef<string | null>(null);

  const resetView = useCallback(() => {
    let targetX = grid_origin_svg_x;
    let targetY = grid_origin_svg_y;

    // Fallback to map center if origin is (0,0) and map dimensions are available
    if (targetX === 0 && targetY === 0 && config.map_width && config.map_height) {
      targetX = config.map_width / 2;
      targetY = config.map_height / 2;
    }

    // Ultimate fallback to projection center if still (0,0)
    if (targetX === 0 && targetY === 0) {
      targetX = centerX;
      targetY = centerY;
    }
    
    const { x: displayX, y: displayY } = rotatePoint(
      targetX,
      targetY,
      centerX,
      centerY,
      rotation
    );
    
    setViewBox({
      x: displayX - 500,
      y: displayY - 375,
      w: 1000,
      h: 750,
    });
  }, [grid_origin_svg_x, grid_origin_svg_y, config.map_width, config.map_height, centerX, centerY, rotation]);

  useLayoutEffect(() => {
    // Only center if we have a map path and it's different from what we last centered on
    // This also ensures we don't center prematurely (e.g. on MenuScene)
    if (config.current_map_path && config.current_map_path !== lastCenteredMapPath.current) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      resetView();
      lastCenteredMapPath.current = config.current_map_path;
    }
  }, [config.current_map_path, resetView]);
```

**Step 2: Run lint to verify**

Run: `npm run lint` in `frontend` directory.
Expected: PASS (no errors).

**Step 3: Commit**

```bash
git add frontend/src/components/SchematicCanvas.tsx
git commit -m "fix(frontend): improve map centering trigger and add fallback to map center"
```

### Task 2: Verify with Playwright E2E Test

**Files:**

- Test: `frontend/e2e/map-centering.spec.ts`

**Step 1: Run the E2E tests**

Run: `npx playwright test e2e/map-centering.spec.ts` in `frontend` directory.
Expected: PASS (2 tests).

**Step 2: Commit (if any fixes were needed in the test)**

```bash
git add frontend/e2e/map-centering.spec.ts
git commit -m "test(frontend): verify map centering and fallback with E2E tests"
```
