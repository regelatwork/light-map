# Feature: Projection Interference Mitigation

## Problem
Projecting on a surface creates intense light that washes out hand features, causing MediaPipe tracking to fail. The camera sees a white blob instead of a hand.

## Goals
Improve hand tracking robustness *without* degrading the visual quality of the projection (e.g., dimming) unless absolutely necessary.

## Proposed Solutions

### 1. Computer Vision Enhancement (Pre-processing)
*   **Concept**: Modify the camera input frame *before* passing it to MediaPipe. The user sees the original frame (or nothing), but the AI sees an enhanced version.
*   **Techniques**:
    *   **Gamma Correction**: Apply `gamma < 1.0` (e.g., 0.5) to "stretch" the shadows and midtones while compressing the highlights. This helps recover details in the "washed out" skin areas.
    *   **CLAHE (Contrast Limited Adaptive Histogram Equalization)**: Boosts local contrast. This helps distinguish the hand's edge from the projected pattern.
    *   **Color Space**: Convert to LAB, apply CLAHE to L-channel, convert back? Or just apply to Gray/V-channel if MediaPipe accepts it (MediaPipe expects RGB).

### 2. Context-Aware Dimming (Backup)
*   **Concept**: Only dim the projection when the user is *trying* to interact but detection is failing.
*   **Trigger**: This is tricky (how do we know they are trying?).
*   **Constraint**: "The main use case of showing the map should not be dimmed."
*   **Strategy**:
    *   If `Menu Mode` is active -> Dimming is allowed to maintain tracking.
    *   If `Map Mode` is active (manipulating) -> Dimming is allowed.
    *   If `Idle/View Mode` -> Full brightness.
    *   **Entry**: To enter interaction from Idle, we rely on **Input Enhancement** to catch the initial "Summon" gesture.

## Implementation Plan

### Phase 1: Vision Enhancer Pipeline
*   **Module**: `src/light_map/vision_enhancer.py`
*   **Class**: `VisionEnhancer`
*   **Methods**:
    *   `apply_gamma(frame, gamma)`
    *   `apply_clahe(frame)`
    *   `enhance(frame)` -> returns processed frame for MediaPipe.
*   **Integration**: Update `hand_tracker.py` to pass the *enhanced* frame to `hands.process()`.
*   **Tuning**: Add `MenuActions` or keyboard shortcuts to adjust Gamma/Contrast live to find the sweet spot.

### Phase 2: Active Dimming (Optional/Later)
*   Implement dimming logic in `InteractiveApp` only when in specific interactive modes.