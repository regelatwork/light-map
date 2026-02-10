# Feature: Projection Interference Mitigation

## Problem
Projecting on a surface creates intense light that washes out hand features, causing MediaPipe tracking to fail. The camera sees a white blob instead of a hand.

## Goals
Improve hand tracking robustness *without* degrading the visual quality of the projection (e.g., dimming) unless absolutely necessary.

## Solutions Implemented

### 1. Computer Vision Enhancement (Pre-processing)
*   **Concept**: Modify the camera input frame *before* passing it to MediaPipe. The user sees the original frame (or nothing), but the AI sees an enhanced version.
*   **Techniques**:
    *   **Gamma Correction**: Apply `gamma < 1.0` (e.g., 0.5) to "stretch" the shadows and midtones while compressing the highlights. This helps recover details in the "washed out" skin areas.
    *   **CLAHE (Contrast Limited Adaptive Histogram Equalization)**: Boosts local contrast in the L-channel (LAB color space). This helps distinguish the hand's edge from the projected pattern.
*   **Live Tuning**: Parameters can be adjusted in real-time using keyboard shortcuts.
*   **Persistence**: Settings are saved to `map_state.json`.

## Implementation Status

### Phase 1: Vision Enhancer Pipeline [DONE]
*   **Module**: `src/light_map/vision_enhancer.py`
*   **Integration**: `hand_tracker.py` passes enhanced frames to MediaPipe.
*   **Controls**:
    *   `[` / `]`: Decrease / Increase Gamma (-/+ 0.1).
    *   `{` / `}`: Decrease / Increase CLAHE Clip Limit (-/+ 0.5).
*   **Debug**: Run with `--view-enhanced` to visualize the AI input.

### Phase 2: Active Dimming (On Hold)
*   *Deferred in favor of successful vision enhancement.*
