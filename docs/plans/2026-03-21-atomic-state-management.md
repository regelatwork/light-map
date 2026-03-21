# Atomic Versioned State & Temporal Management Implementation Plan

> **For Gemini:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transition the monolithic `WorldState` to a decentralized, Atomic State architecture with a centralized `TemporalEventManager`.

**Architecture:** Replace manual timestamp management with `VersionedAtom` objects that automatically track changes using monotonic timestamps. `WorldState` becomes a registry of these atoms, and `TemporalEventManager` becomes the sole authority for time-based state updates.

**Tech Stack:** Python 3.10+, NumPy, OpenCV (for rendering pipeline integration).

---

### Task 1: Core Implementation: `VersionedAtom`

**Files:**
- Create: `src/light_map/core/versioned_atom.py`
- Test: `tests/test_versioned_atom.py`

**Step 1: Write the failing test**

```python
import time
from light_map.core.versioned_atom import VersionedAtom

def test_versioned_atom_updates_timestamp_on_change():
    atom = VersionedAtom(10, "test_atom")
    initial_ts = atom.timestamp
    
    time.sleep(0.001) # Ensure monotonic clock can advance
    changed = atom.update(20)
    
    assert changed is True
    assert atom.value == 20
    assert atom.timestamp > initial_ts

def test_versioned_atom_does_not_update_on_same_value():
    atom = VersionedAtom(10, "test_atom")
    initial_ts = atom.timestamp
    
    changed = atom.update(10)
    
    assert changed is False
    assert atom.timestamp == initial_ts
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_versioned_atom.py -v`
Expected: FAIL (Module not found)

**Step 3: Write minimal implementation**

```python
import time
from typing import TypeVar, Generic, Optional, Callable

T = TypeVar("T")

class VersionedAtom(Generic[T]):
    def __init__(self, initial_value: T, name: str, equality_fn: Optional[Callable[[T, T], bool]] = None):
        self._value = initial_value
        self._name = name
        self._timestamp = time.monotonic_ns()
        self._equality_fn = equality_fn or (lambda a, b: a == b)

    @property
    def value(self) -> T:
        return self._value

    @property
    def timestamp(self) -> int:
        return self._timestamp

    def update(self, new_value: T, force_timestamp: Optional[int] = None) -> bool:
        if force_timestamp is not None or not self._equality_fn(self._value, new_value):
            self._value = new_value
            self._timestamp = force_timestamp or time.monotonic_ns()
            return True
        return False
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_versioned_atom.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/light_map/core/versioned_atom.py tests/test_versioned_atom.py
git commit -m "feat: implement VersionedAtom core class"
```

---

### Task 2: Transaction Support in WorldState

**Files:**
- Modify: `src/light_map/core/world_state.py`
- Test: `tests/test_world_state_transactions.py`

**Step 1: Write the failing test**

```python
from light_map.core.world_state import WorldState
from light_map.core.versioned_atom import VersionedAtom

def test_world_state_transaction_batches_timestamps():
    state = WorldState()
    # Mocking atoms for the test since they aren't in WorldState yet
    state.atom1 = VersionedAtom(1, "atom1")
    state.atom2 = VersionedAtom(2, "atom2")
    
    with state.transaction() as tx:
        tx.update(state.atom1, 10)
        tx.update(state.atom2, 20)
        
    assert state.atom1.value == 10
    assert state.atom2.value == 20
    assert state.atom1.timestamp == state.atom2.timestamp
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_world_state_transactions.py -v`
Expected: FAIL (AttributeError: 'WorldState' object has no attribute 'transaction')

**Step 3: Write minimal implementation**

```python
# In src/light_map/core/world_state.py
from contextlib import contextmanager
from .versioned_atom import VersionedAtom

class Transaction:
    def __init__(self, timestamp: int):
        self.timestamp = timestamp

    def update(self, atom: VersionedAtom, new_value: Any):
        atom.update(new_value, force_timestamp=self.timestamp)

class WorldState:
    # ... existing __init__ ...
    
    @contextmanager
    def transaction(self):
        ts = time.monotonic_ns()
        yield Transaction(ts)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_world_state_transactions.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/light_map/core/world_state.py tests/test_world_state_transactions.py
git commit -m "feat: add transaction support to WorldState"
```

---

### Task 3: Phase 1 Migration: Viewport & Menu State

**Files:**
- Modify: `src/light_map/core/world_state.py`
- Test: `tests/test_world_state_atomic.py`

**Step 1: Write the failing test**

```python
from light_map.core.world_state import WorldState
from light_map.common_types import ViewportState

def test_viewport_is_atomic():
    state = WorldState()
    assert hasattr(state.viewport, "timestamp")
    assert isinstance(state.viewport.value, ViewportState)

def test_update_viewport_updates_atom():
    state = WorldState()
    new_vp = ViewportState(x=100)
    state.update_viewport(new_vp)
    assert state.viewport.value.x == 100
    assert state.viewport_timestamp == state.viewport.timestamp
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_world_state_atomic.py -v`
Expected: FAIL (AttributeError: 'ViewportState' object has no attribute 'timestamp')

**Step 3: Write minimal implementation**

```python
# In src/light_map/core/world_state.py
class WorldState:
    def __init__(self, ...):
        # ...
        self._viewport_atom = VersionedAtom(ViewportState(), "viewport")
        self._menu_state_atom = VersionedAtom(None, "menu_state")
        
    @property
    def viewport(self) -> ViewportState:
        return self._viewport_atom.value
        
    @property
    def viewport_timestamp(self) -> int:
        return self._viewport_atom.timestamp

    def update_viewport(self, new_viewport: ViewportState):
        self._viewport_atom.update(new_viewport)

    # Repeat for menu_state...
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_world_state_atomic.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/light_map/core/world_state.py
git commit -m "refactor: migrate viewport and menu_state to VersionedAtom"
```

---

### Task 4: Temporal Authority: Upgrade TemporalEventManager

**Files:**
- Modify: `src/light_map/core/temporal_event_manager.py`
- Modify: `src/light_map/core/world_state.py`
- Test: `tests/test_temporal_authority.py`

**Step 1: Write the failing test**

```python
from light_map.core.world_state import WorldState
from light_map.core.temporal_event_manager import TemporalEventManager

def test_temporal_manager_updates_system_time():
    state = WorldState()
    tem = TemporalEventManager(state)
    
    initial_time = state.system_time
    tem.advance(1.0) # Mock time advancement
    
    assert state.system_time > initial_time
    assert state.system_time_timestamp > 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_temporal_authority.py -v`
Expected: FAIL (WorldState has no system_time)

**Step 3: Write minimal implementation**

```python
# In WorldState:
self._system_time_atom = VersionedAtom(0.0, "system_time")

# In TemporalEventManager:
def __init__(self, state: WorldState, ...):
    self.state = state
    # ...

def advance(self, dt: float):
    new_time = self.state.system_time + dt
    self.state._system_time_atom.update(new_time)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_temporal_authority.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/light_map/core/temporal_event_manager.py src/light_map/core/world_state.py
git commit -m "feat: give TemporalEventManager authority over system_time"
```

---

### Task 5: Phase 2 Migration: Tokens & Blockers

**Files:**
- Modify: `src/light_map/core/world_state.py`
- Test: `tests/test_tokens_atomic.py`

**Step 1: Write the failing test**

```python
from light_map.core.world_state import WorldState
from light_map.common_types import Token

def test_tokens_use_optimized_equality():
    state = WorldState()
    t1 = Token(id=1, world_x=10, world_y=10)
    state.tokens = [t1]
    ts1 = state.tokens_timestamp
    
    # Update with semantically identical token (tiny jitter)
    t1_jitter = Token(id=1, world_x=10.1, world_y=10.1)
    state.tokens = [t1_jitter]
    
    assert state.tokens_timestamp == ts1 # Should NOT change
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_tokens_atomic.py -v`
Expected: FAIL (Timestamps differ or tokens not atomic)

**Step 3: Write minimal implementation**

```python
# In WorldState:
def _tokens_equal(self, old: List[Token], new: List[Token]) -> bool:
    # Use existing _tokens_equal logic but ensure it's used by the atom
    return self._old_tokens_equal(old, new)

self._tokens_atom = VersionedAtom([], "tokens", equality_fn=self._tokens_equal)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_tokens_atomic.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/light_map/core/world_state.py
git commit -m "refactor: migrate tokens and blockers to VersionedAtom"
```

---

### Task 6: Rendering Pipeline Update (MapLayer)

**Files:**
- Modify: `src/light_map/map_layer.py`
- Test: `tests/test_map_layer_atomic.py`

**Step 1: Write the failing test**

```python
# Verify MapLayer.get_current_version() uses atomic timestamps correctly
```

**Step 2: Run test to verify it fails**

**Step 3: Write minimal implementation**

```python
# Update MapLayer.get_current_version to use self.state.viewport_timestamp 
# which is now coming from the atom.
```

**Step 4: Run test to verify it passes**

**Step 5: Commit**

```bash
git add src/light_map/map_layer.py
git commit -m "refactor: update MapLayer to use atomic versioning"
```

---

### Task 7: Cleanup & Deprecation

**Files:**
- Modify: `src/light_map/core/world_state.py`

**Step 1: Remove legacy `_get_next_version` and manual timestamp updates.**

**Step 2: Run all tests to ensure no regressions.**

**Step 3: Commit.**

```bash
git add src/light_map/core/world_state.py
git commit -m "cleanup: remove legacy timestamp management"
```
