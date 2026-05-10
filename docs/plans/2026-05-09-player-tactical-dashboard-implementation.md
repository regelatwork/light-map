# Player Tactical Dashboard Implementation Plan

> **For Gemini:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a mobile-optimized, text-centric frontend for players to claim PC tokens, control tabletop exclusive vision, and view live tactical bonuses.

**Architecture:** Extend the `RemoteDriver` with REST endpoints for vision and pings. The `ActionDispatcher` handles these by updating `WorldState` and triggering `TemporalEventManager`. A new `PingLayer` reactively renders pings from `WorldState`. The `state_mirror` is updated to broadcast a flattened `tactical` object.

**Tech Stack:** Python (FastAPI, Numba), React (TypeScript, Tailwind CSS), WebSockets.

---

### Task 1: Backend - Define Models and Action Types

**Files:**
- Modify: `src/light_map/core/common_types.py`
- Modify: `src/light_map/vision/remote/remote_driver.py`

**Step 1: Update Action Enum**
Add `TRIGGER_PING` and `TOGGLE_EXCLUSIVE_VISION` to the `Action` enum in `src/light_map/core/common_types.py`.

**Step 2: Define Pydantic Models**
In `src/light_map/vision/remote/remote_driver.py`, define:
```python
class PingRequest(BaseModel):
    token_id: str  # The ID of the token being pinged

class VisionRequest(BaseModel):
    token_id: str | None  # ID of PC to lock vision on, or None to clear
```

**Step 3: Commit**
```bash
git add src/light_map/core/common_types.py src/light_map/vision/remote/remote_driver.py
git commit -m "feat(types): define models and action types for player dashboard"
```

---

### Task 2: Backend - PingLayer and Action Handling

**Files:**
- Modify: `src/light_map/state/world_state.py`
- Create: `src/light_map/rendering/layers/ping_layer.py`
- Modify: `src/light_map/core/layer_stack_manager.py`
- Modify: `src/light_map/action_dispatcher.py`
- Test: `tests/test_ping_logic.py`

**Step 1: Update WorldState for Pings**
Add an `active_pings` atom (a `dict` mapping `token_id` to `timestamp`) to `WorldState` and include it in `to_dict()`.

**Step 2: Implement PingLayer**
Create `src/light_map/rendering/layers/ping_layer.py` inheriting from `Layer`. It should:
- Read `state.active_pings`.
- For each ping, calculate `elapsed = current_time - timestamp`.
- If `elapsed < 2.0`, render a pulsing ring (interpolating radius and alpha based on `elapsed`) at the token's coordinates.

**Step 3: Register Layer**
Add `PingLayer` to the `layer_stack` in `LayerStackManager.py`, ensuring it renders above the map but below menus.

**Step 4: Implement Action Handlers**
In `ActionDispatcher.py`:
- `handle_trigger_ping(app, payload, state)`:
    - Get `token_id` from payload.
    - Update `state.active_pings` using `atom.update()` to ensure a version bump and re-render.
    - Use `app.events.schedule(2.0, lambda: state.active_pings.update(lambda p: {k: v for k, v in p.items() if k != token_id}))` to clean up.
- `handle_toggle_exclusive_vision(app, payload, state)`:
    - Get `token_id` from payload.
    - If `token_id` is provided:
        - Set `state.selection` to the provided `token_id`.
        - Trigger `app.scene_manager.transition_to(SceneId.EXCLUSIVE_VISION)`.
    - If `token_id` is `None`:
        - Clear selection and `app.scene_manager.transition_to(SceneId.VIEWING)`.

**Step 5: Test and Commit**
```bash
git add .
git commit -m "feat(backend): implement PingLayer and ActionDispatcher handlers"
```

---

### Task 3: Backend - API and State Mirror

**Files:**
- Modify: `src/light_map/vision/remote/remote_driver.py`
- Modify: `src/light_map/state/world_state.py`

**Step 1: Implement REST Endpoints**
In `remote_driver.py`, add:
- `POST /actions/exclusive-vision`: Injects `Action.TOGGLE_EXCLUSIVE_VISION` with `VisionRequest` payload.
- `POST /actions/ping`: Injects `Action.TRIGGER_PING` with `PingRequest` payload.

**Step 2: Define state_mirror 'tactical' object**
Update `WorldState.to_dict()` (or a helper) to produce:
```json
"tactical": {
    "attacker_id": str | None,
    "is_exclusive_active": bool,
    "targets": [
        {"id": str, "name": str, "ac_bonus": int, "reflex_bonus": int, "reason": str}
    ]
}
```
Populate this from `state.selection` and `state.tactical_bonuses`.

**Step 3: Update RemoteDriver State Broadcast**
Ensure `get_formatted_state` in `remote_driver.py` includes this new `tactical` key.

**Step 4: Commit**
```bash
git add src/light_map/vision/remote/remote_driver.py src/light_map/state/world_state.py
git commit -m "feat(api): finalize player API and tactical state broadcast"
```

---

### Task 4: Frontend - Player Dashboard UI

**Files:**
- Create: `frontend/src/apps/PlayerDashboard/PlayerApp.tsx`
- Create: `frontend/src/apps/PlayerDashboard/CharacterSelector.tsx`
- Create: `frontend/src/apps/PlayerDashboard/TacticalList.tsx`

**Step 1: Character Selector**
Fetch all `PC` tokens from `state_mirror.config.tokens` and allow the user to select one, saving to `localStorage`.

**Step 2: Tactical List & Actions**
- Subscribe to `state_mirror` at 1Hz.
- Display the `tactical.targets` list.
- Add "Vision" toggle and "Ping" buttons for each target.

**Step 3: Commit**
```bash
git add frontend/src/apps/PlayerDashboard/
git commit -m "feat(frontend): implement Player Dashboard UI"
```
