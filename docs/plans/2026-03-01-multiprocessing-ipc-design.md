# Design Document: Multiprocessing IPC (N+2 Buffer Strategy)

**Date**: 2026-03-01
**Status**: Validated
**Related**: `features/multiprocessing_refactor.md`

## Overview

This document defines the Inter-Process Communication (IPC) mechanism for sharing high-resolution camera frames between the `CameraOperator` (Producer) and multiple `FrameProducer` instances (Consumers). To overcome the performance bottlenecks of Python's GIL and the overhead of frame serialization, we use a Shared Memory architecture with an **$N+2$ Buffer Strategy**.

## Architecture

The system utilizes a single `multiprocessing.shared_memory` block, partitioned into a **Control Block** and **Frame Data**.

### Shared Memory Layout

1. **Control Block (Locked Access)**:

   - **`ref_counts`**: An array of $N+2$ integers.
     - `-1`: Reserved for writing (Producer only).
     - `0`: Idle/Available for overwrite.
     - `1+`: Active readers (number of consumers holding a lease).
   - **`timestamps`**: An array of $N+2$ 64-bit integers (microseconds).
   - **`latest_buffer_id`**: Integer pointing to the most recent valid frame (initial: `-1`).
   - **`lock`**: A `multiprocessing.Lock` synchronizing all state changes.

1. **Frame Data**:

   - $N+2$ contiguous segments, each sized for one raw frame (e.g., $1920 imes 1080 imes 3$ bytes).

### The $N+2$ Guarantee

With $N$ consumers, we guarantee the Producer always has a buffer to write into:

- $N$ buffers potentially held by busy consumers.
- $1$ buffer representing the "Latest" frame available for new requests.
- $1$ buffer available for the Producer to write the next incoming frame.

## Component Logic

### CameraOperator (Producer)

1. **Find Buffer**: Iterate through `ref_counts` to find the first index with `0`.
1. **Reserve**: Atomically set `ref_counts[index] = -1`.
1. **Write**: Capture frame directly into the shared memory segment.
1. **Publish**:
   - **Lock** control block.
   - Update `timestamps[index]`.
   - Set `latest_buffer_id = index`.
   - Set `ref_counts[index] = 0` (making it available for consumers).
   - **Unlock**.

### FrameProducer (Consumer)

Each consumer process maintains a local `_current_buffer_id` (initial: `None`).

#### `get_latest_timestamp() -> Optional[int]`

1. **Lock** control block.
1. If `latest_buffer_id == -1`, return `None`.
1. Return `timestamps[latest_buffer_id]`.
1. **Unlock**.

#### `get_latest_frame() -> Optional[np.ndarray]`

1. **Verify State**: If `_current_buffer_id` is NOT `None`, raise `RuntimeError` (must call `release()` first).
1. **Lock** control block.
1. If `latest_buffer_id == -1`, **Unlock** and return `None`.
1. **Acquire**:
   - Set `target_id = latest_buffer_id`.
   - Increment `ref_counts[target_id]`.
   - Set local `_current_buffer_id = target_id`.
1. **Unlock**.
1. Return a NumPy view of the shared memory segment.

#### `release()`

1. If `_current_buffer_id` is `None`, return immediately.
1. **Lock** control block.
1. **Decrement** `ref_counts[_current_buffer_id]`.
1. Set local `_current_buffer_id = None`.
1. **Unlock**.

## Error Handling & Lifecycle

- **Cold Start**: Consumers receive `None` from `get_latest_frame()` until the first frame is published.
- **Strict Lifecycle**: The `Acquire -> Process -> Release` pattern is enforced to prevent buffer exhaustion.
- **Producer Stall Prevention**: If no `0` ref_count buffer is found, the Producer may overwrite the `latest_buffer_id` if its ref_count is `0`, ensuring the stream never blocks.
