# Plan: Sort PC Tokens Alphabetically in CharacterSelector and List NPCs before PCs in TacticalList

> **For Gemini:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

## 1. Overview & Architectural Boundaries

This blueprint outlines the architectural changes required to improve the user experience on the Light Map Player Dashboard:

1. **CharacterSelector**: Sort PC tokens alphabetically by character name before rendering them in the hero selection UI.
1. **TacticalList**: Ensure NPCs appear before PCs in the visible targets list on the player's tactical dashboard.

### Architectural Boundaries

- **State Source of Truth**: `WorldState` in the Python backend owns token metadata (including `type`: `"PC"` | `"NPC"`).
- **API & Mirror Broadcast**: `WorldState.to_dict()` serializes target information for the state mirror / WebSocket stream consumed by the React frontend (`PlayerApp`).
- **Presentation Component Logic**: Sorting logic for PC token selection is encapsulated within `CharacterSelector.tsx`. Target sorting by entity type (`NPC` vs `PC`) is encapsulated within `TacticalList.tsx` / `PlayerApp.tsx`.

______________________________________________________________________

## 2. Domain Analysis & Design Trade-offs

### 2.1 CharacterSelector Alphabetical Sorting

- **Current Behavior**: `CharacterSelector.tsx` fetches token configurations from `/config` (`aruco_defaults`), filters by `type === 'PC'`, and renders them in whatever key insertion order the object entries are returned.
- **New Requirement**: Sort the filtered PC tokens alphabetically by character name (e.g. using `localeCompare` with sensitivity set to base/accent-insensitive).
- **Edge Cases**:
  - Unnamed tokens default to `Token ${id}` or `id`. Sorting logic must evaluate the resolved display name (`pc.name || Token ${pc.id}`).
  - Case sensitivity: Use `String.prototype.localeCompare(..., undefined, { numeric: true, sensitivity: 'base' })` for natural sorting (e.g., "Hero 2" before "Hero 10").

### 2.2 TacticalList Entity Ordering (NPCs before PCs)

- **Current Behavior**: `WorldState.to_dict()` outputs `tactical.targets` containing `id`, `name`, `ac_bonus`, `reflex_bonus`, and `reason`. The frontend `TacticalList.tsx` maps over `targets` directly without entity type awareness.
- **New Requirement**: Ensure NPCs are listed before PCs in `TacticalList`.
- **Data Contract Update**:
  - Update `WorldState.to_dict()` in `src/light_map/state/world_state.py` to include `"type": next((t.type for t in self.tokens if t.id == target_id), "NPC")` in each target dictionary.
  - Update frontend TypeScript interfaces (`TacticalTarget` in `PlayerApp.tsx` and `Target` in `TacticalList.tsx`) to include `type?: string`.
- **Sorting Logic**:
  - In `TacticalList.tsx` (or `PlayerApp.tsx`), sort `targets` such that targets with `type === 'NPC'` come before targets with `type === 'PC'`.
  - Maintain a secondary sort by `name` alphabetically for consistency.

______________________________________________________________________

## 3. Detailed Data Contracts

### Backend `WorldState.to_dict()` Target Schema

```json
{
  "tactical": {
    "attacker_id": "1",
    "is_exclusive_active": true,
    "targets": [
      {
        "id": "2",
        "name": "Goblin Scout",
        "type": "NPC",
        "ac_bonus": 2,
        "reflex_bonus": 1,
        "reason": "Partial Cover"
      },
      {
        "id": "3",
        "name": "Valeros",
        "type": "PC",
        "ac_bonus": 0,
        "reflex_bonus": 0,
        "reason": "Clear Line of Sight"
      }
    ]
  }
}
```

### Frontend TypeScript Definitions

```typescript
// frontend/src/apps/PlayerDashboard/TacticalList.tsx
export interface Target {
  id: string;
  name: string;
  type?: string; // 'NPC' | 'PC'
  ac_bonus: number;
  reflex_bonus: number;
  reason: string;
}

// frontend/src/apps/PlayerDashboard/PlayerApp.tsx
interface TacticalTarget {
  id: number | string;
  name: string;
  type?: string;
  ac_bonus: number;
  reflex_bonus: number;
  reason: string;
}
```

______________________________________________________________________

## 4. Implementation Tasks

### Task 1: Backend - Include `type` in `tactical.targets` State Serialization

**Files:**

- Modify: `src/light_map/state/world_state.py`
- Test: `tests/test_remote_driver_tactical.py` or new test in `tests/`

**Steps:**

1. In `src/light_map/state/world_state.py` inside `to_dict()`, update the `tactical.targets` dictionary construction to include `"type"`:
   ```python
   "type": next((t.type for t in self.tokens if t.id == target_id), "NPC"),
   ```
1. Add a unit test verifying `WorldState.to_dict()` outputs the `type` field for tactical targets.

______________________________________________________________________

### Task 2: Frontend - Alphabetical PC Sorting in `CharacterSelector`

**Files:**

- Modify: `frontend/src/apps/PlayerDashboard/CharacterSelector.tsx`
- Test: `frontend/src/apps/PlayerDashboard/CharacterSelector.test.tsx`

**Steps:**

1. In `CharacterSelector.tsx`, after mapping PC tokens from `aruco_defaults`, sort the array:
   ```typescript
   pcs.sort((a, b) => {
     const nameA = a.name || `Token ${a.id}`;
     const nameB = b.name || `Token ${b.id}`;
     return nameA.localeCompare(nameB, undefined, { numeric: true, sensitivity: 'base' });
   });
   ```
1. Write unit tests in `CharacterSelector.test.tsx`:
   - Test that PC tokens fetched out-of-order (e.g. Wizard, Fighter, Cleric) are rendered in alphabetical order (Cleric, Fighter, Wizard).

______________________________________________________________________

### Task 3: Frontend - NPC Before PC Ordering in `TacticalList`

**Files:**

- Modify: `frontend/src/apps/PlayerDashboard/TacticalList.tsx`
- Modify: `frontend/src/apps/PlayerDashboard/PlayerApp.tsx`
- Test: `frontend/src/apps/PlayerDashboard/PlayerApp.test.tsx`
- Create/Modify: `frontend/src/apps/PlayerDashboard/TacticalList.test.tsx`

**Steps:**

1. Update `Target` and `TacticalTarget` interfaces to include `type?: string`.
1. In `TacticalList.tsx` (or prior to passing `targets` to `TacticalList`), sort the list of targets:
   ```typescript
   const sortedTargets = [...targets].sort((a, b) => {
     const typeA = (a.type || 'NPC').toUpperCase();
     const typeB = (b.type || 'NPC').toUpperCase();
     if (typeA !== typeB) {
       // 'NPC' should come before 'PC'
       return typeA === 'NPC' ? -1 : 1;
     }
     // Secondary sort by target name
     return a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: 'base' });
   });
   ```
1. Add tests in `TacticalList.test.tsx` and `PlayerApp.test.tsx` verifying that when both PC and NPC targets are present, NPCs render first in the DOM list.

______________________________________________________________________

### Task 4: Mandated Formatting, Verification & Checkpoint

**Steps:**

1. Format & lint backend Python code:
   ```bash
   ruff format .
   ruff check . --fix
   mdformat .
   ```
1. Run backend test suite:
   ```bash
   pytest
   ```
1. Run frontend test suite:
   ```bash
   npm --prefix frontend test
   ```
