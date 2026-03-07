# Feature: Hand Tracking Masking

## Problem

Hand tracking can be negatively affected by two main factors in this project:

1. **Projector Interference**: Projected light from the digital tabletop often falls directly onto the user's hands, causing sensor saturation and color distortion.
1. **Environmental Noise**: Players and the GM sitting around the table may have their hands near the map, causing accidental triggers of menus or interactions when they are just reaching for a snack or resting their arms.

## Goal

Implement a comprehensive **Hand Tracking Masking** system that addresses both issues:

- **Dynamic Projection Masking ("Digital Shadow")**: Selectively "black out" the area of the projected image where the user's hands are located to preserve tracking robustness.
- **Interactive Input Restriction**: Mask out specific regions of the camera's field of view (or ignore detections) to prevent accidental interactions from non-active players/GM.

## Proposed Solution 1: The "Digital Shadow" (Projection Masking)

We will utilize the hand landmark data from the vision pipeline to generate a dynamic mask that is applied to the final projected frame.

### 1. Mask Generation

- **Input**: Hand landmarks (normalized camera coordinates) from the most recent vision frame.
- **Multi-Hand Support**: Generate masks for all detected hands (typically up to 2).
- **Confidence Threshold**: Only generate a mask if the MediaPipe tracking confidence exceeds a configurable threshold (e.g., 0.7) to avoid masking based on "ghost" detections.
- **Transformation**: Convert camera coordinates to projector coordinates using the established homography and distortion correction model.
- **Shape**:
  - **Primary**: **Convex Hull** of all detected landmarks. This provides a tight, aesthetically pleasing silhouette of the hand.
  - **Fallback**: Bounding box if hull computation is too expensive (unlikely given OpenCV's efficiency).
- **Padding**: Add a configurable buffer (e.g., 20-50 pixels) around the detected hand to account for latency and hand thickness.

### 2. Application

- The mask will be a black (BGR: 0,0,0) region drawn on top of the rendered map/UI before it is sent to the projector.
- **Feathering**: Optionally apply a slight blur (Gaussian) to the mask edges to make the "shadow" look more natural on the table.
- **Interaction with Dimming**: Hand masking should remain active even when the map is dimmed (e.g., during Panning), as the dimmed light can still cause interference.

## Proposed Solution 2: Interactive Input Restriction (Input Masking)

To prevent accidental interactions, we will allow the user to define "Safe Zones" or "Exclusion Zones" for hand tracking.

### 1. GM-Location Based Masking

The system supports a configurable "GM Position" to filter out accidental hand detections from players or environment noise outside the active map area.

**Logic**:

- **Interior Protection**: Any hand detection with its index tip **inside** the projector's active area (the map/UI region) is **always allowed**. This ensures that once a hand is over the interactive surface, it remains usable regardless of which side it entered from.
- **Exterior Filtering**: Hands detected **outside** the projector's active area are **masked (ignored)** by default.
- **GM Side Exemption**: If a `gm_position` is set (e.g., `NORTH`), hands detected on that specific side of the exterior are **unmasked**. This allows the GM to perform "Summon" gestures or prepare interactions from their seated position even before their hand enters the projected map area.

**GM Positions and Allowed Exterior Sides:**

| GM Position | Allowed Exterior Sides |
| :--- | :--- |
| `NONE` | None (All exterior masked) |
| `NORTH` | North (y < 0) |
| `SOUTH` | South (y >= height) |
| `EAST` | East (x >= width) |
| `WEST` | West (x < 0) |
| `NORTH_WEST`| North, West |
| `NORTH_EAST`| North, East |
| `SOUTH_WEST`| South, West |
| `SOUTH_EAST`| South, East |

### 2. Digital Shadow (Projection Masking) Details

- **Hull Buffer**: 2cm physical expansion (calculated using `config.projector_ppi`).
- **Blur Radius**: 15 pixels (default).
- **Latency Compensation**: None initially, rely on padding.
- **Persistence**: **1.0 second**. If tracking is lost, keep the last mask for up to 1 second to avoid "flash" of light on the hand.

## Technical Implementation Plan

### Phase 1: Hand Masker Utility

1. Create `src/light_map/vision/hand_masker.py`.
1. Implement a `HandMasker` class that:
   - Handles both Projection Masking (Digital Shadow) and Input Masking (Filtering).
   - Takes hand landmarks and project settings.
   - Computes the convex hull in projector space.
   - **Persistence**: Uses a time-based approach (default 1.0s) to maintain the last known hulls during tracking jitter.
   - Generates a mask image or provides a `is_point_masked(x, y)` check.

### Phase 2: Input Processor & Renderer Integration

1. Update `InputProcessor` to filter out detected hands if they fall in the masked input zones.
1. Update `HandMaskLayer` to call `hand_masker.get_mask_hulls()`.
1. Ensure the mask is applied *after* map and scene rendering but before UI overlays.

### Phase 3: Configuration & Tuning

1. Add `enable_hand_masking`, `hand_mask_padding`, and `input_mask_mode` to `AppConfig`.
1. Add toggle and selection entries in the menu system.

## Success Criteria

- [x] Hand tracking remains stable even when hovering over bright white map regions.
- [x] The "digital shadow" follows the hand with minimal perceptible lag.
- [x] Accidental hand movements from non-GM sides of the table (outside the map) do not trigger UI actions.
- [x] The menu and map remain fully interactive regardless of GM position (interior is never masked).
- [x] The mask is correctly aligned with the physical hand on the table.
