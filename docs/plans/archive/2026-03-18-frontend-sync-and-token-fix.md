# Frontend State Synchronization and Token Resolution Fix Implementation Plan

> **For Gemini:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Resolve frontend synchronization issues (menu, parallax) and fix the "all tokens are NPC" bug by optimizing IPC communication, improving change detection, and making config resolution more robust.

**Architecture:**

1. **Throttled State Mirror**: Update `state_mirror` in the main loop only when version timestamps change or at a fixed interval, reducing `multiprocessing.Manager` contention.
1. **Granular Change Detection**: Expand the `if` block in `render_cb` to track all `AppConfig` fields that affect the frontend.
1. **Async-Safe Remote Driver**: Use `asyncio.to_thread` for blocking `state_mirror.get()` calls in the WebSocket broadcast loop.
1. **Proactive Token Resolution**: Resolve unknown ArUco IDs before mapping to ensure correct types are assigned immediately.

**Tech Stack:** Python (FastAPI, WebSockets, Multiprocessing), React (Vite).

______________________________________________________________________

### Task 1: Fix Config Change Detection in render_cb

**Files:**

- Modify: `src/light_map/__main__.py`

**Step 1: Expand the change detection condition**
Add `parallax_factor`, `gm_position`, `enable_hand_masking`, and `enable_aruco_masking` to the tracked variables.

**Step 2: Ensure all trackers are updated**
Add `last_parallax_factor`, `last_gm_position`, `last_hand_masking`, `last_aruco_masking` to the `nonlocal` scope and update them at the end of the block.

**Step 3: Commit**

```bash
git add src/light_map/__main__.py
git commit -m "fix: expand config change detection in render_cb"
```

### Task 2: Throttle state_mirror Updates

**Files:**

- Modify: `src/light_map/__main__.py`

**Step 1: Track versions in render_cb**
Use `state.world_timestamp`, `state.tokens_timestamp`, and `state.menu_timestamp` to decide when to update `state_mirror`.

**Step 2: Implement throttling**
Only update `state_mirror["world"]`, `state_mirror["tokens"]`, and `state_mirror["menu"]` if their respective timestamps have changed.

**Step 3: Commit**

```bash
git add src/light_map/__main__.py
git commit -m "perf: throttle state_mirror updates using version timestamps"
```

### Task 3: Optimize Remote Driver Broadcast Loop

**Files:**

- Modify: `src/light_map/vision/remote_driver.py`

**Step 1: Use to_thread for blocking calls**
Wrap `state_mirror.get()` calls in `asyncio.to_thread` to avoid blocking the FastAPI event loop.

**Step 2: Reduce IPC frequency**
Cache values from `state_mirror` if they haven't changed (though this is secondary to `to_thread`).

**Step 3: Commit**

```bash
git add src/light_map/vision/remote_driver.py
git commit -m "perf: use to_thread for blocking state_mirror access in broadcast loop"
```

### Task 4: Fix Proactive Token Resolution

**Files:**

- Modify: `src/light_map/vision/tracking_coordinator.py`

**Step 1: Resolve unknown IDs before mapping**
Iterate over `raw_data["ids"]` and resolve any unknown IDs in `token_configs` *before* calling `aruco_detector.map_to_tokens`.

**Step 2: Commit**

```bash
git add src/light_map/vision/tracking_coordinator.py
git commit -m "fix: resolve unknown ArUco IDs before mapping to tokens"
```

### Task 5: Robust Config Loading Fallback

**Files:**

- Modify: `src/light_map/map_config.py`

**Step 1: Add fallback for tokens.json**
If `tokens.json` is not found in the managed config directory, check the project root as a fallback.

**Step 2: Commit**

```bash
git add src/light_map/map_config.py
git commit -m "fix: add project root fallback for tokens.json loading"
```

### Task 6: Verification

**Step 1: Run backend tests**
`pytest tests/test_remote_driver_*.py tests/test_map_config.py`

**Step 2: Manual Verification (Simulated)**
If possible, run the app and verify the logs show correct resolution.
since I can't see the UI, I'll rely on tests and logical verification.
