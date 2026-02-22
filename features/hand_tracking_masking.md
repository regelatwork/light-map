# Feature: Hand Tracking Masking

## Problem

Hand tracking can be negatively affected by two main factors in this project:
1.  **Projector Interference**: Projected light from the digital tabletop often falls directly onto the user's hands, causing sensor saturation and color distortion.
2.  **Environmental Noise**: Players and the GM sitting around the table may have their hands near the map, causing accidental triggers of menus or interactions when they are just reaching for a snack or resting their arms.

## Goal

Implement a comprehensive **Hand Tracking Masking** system that addresses both issues:
-   **Dynamic Projection Masking ("Digital Shadow")**: Selectively "black out" the area of the projected image where the user's hands are located to preserve tracking robustness.
-   **Interactive Input Restriction**: Mask out specific regions of the camera's field of view (or ignore detections) to prevent accidental interactions from non-active players/GM.

## Proposed Solution 1: The "Digital Shadow" (Projection Masking)

We will utilize the hand landmark data from the vision pipeline to generate a dynamic mask that is applied to the final projected frame.

### 1. Mask Generation

-   **Input**: Hand landmarks (normalized camera coordinates) from the most recent vision frame.
-   **Multi-Hand Support**: Generate masks for all detected hands (typically up to 2).
-   **Confidence Threshold**: Only generate a mask if the MediaPipe tracking confidence exceeds a configurable threshold (e.g., 0.7) to avoid masking based on "ghost" detections.
-   **Transformation**: Convert camera coordinates to projector coordinates using the established homography and distortion correction model.
-   **Shape**:
    -   **Primary**: **Convex Hull** of all detected landmarks. This provides a tight, aesthetically pleasing silhouette of the hand.
    -   **Fallback**: Bounding box if hull computation is too expensive (unlikely given OpenCV's efficiency).
-   **Padding**: Add a configurable buffer (e.g., 20-50 pixels) around the detected hand to account for latency and hand thickness.

### 2. Application

-   The mask will be a black (BGR: 0,0,0) region drawn on top of the rendered map/UI before it is sent to the projector.
-   **Feathering**: Optionally apply a slight blur (Gaussian) to the mask edges to make the "shadow" look more natural on the table.
-   **Interaction with Dimming**: Hand masking should remain active even when the map is dimmed (e.g., during Panning), as the dimmed light can still cause interference.

## Proposed Solution 2: Interactive Input Restriction (Input Masking)

To prevent accidental interactions, we will allow the user to define "Safe Zones" or "Exclusion Zones" for hand tracking.

### 1. GM-Location Based Masking

The system will support a configurable "GM Position" that automatically masks out the sides of the table where players are likely to be.

**GM Positions and Masked Sides:**

| GM Position | Unmasked Sides (Active) | Masked Sides (Ignored) |
| :--- | :--- | :--- |
| `NONE` | All | None |
| `NORTH` | North | South, East, West |
| `SOUTH` | South | North, East, West |
| `EAST` | East | North, South, West |
| `WEST` | West | North, South, East |
| `NORTH_WEST`| North, West | South, East |
| `NORTH_EAST`| North, East | South, West |
| `SOUTH_WEST`| South, West | North, East |
| `SOUTH_EAST`| South, East | North, West |

**Logic**:
-   The "Interactive Area" is defined by the projector's homography quad in camera space.
-   A "Side Mask" is a region extending from the edge of the homography quad outwards (or a portion of the quad itself if we want to be strict).
-   Actually, the most robust way is to define the "Unmasked Region" as a subset of the camera frame.
-   If `gm_position` is `NORTH`, the unmasked region is the top half (or top third) of the projector area? No, players reach *into* the map.
-   Better: If a hand landmark (index tip) enters from a masked side and stays near the edge, it is ignored.
-   Even better: Any hand detection whose *origin* or *majority of landmarks* are in a masked quadrant are ignored.
-   **Simplified Requirement**: The user wants to "Mask out areas outside of the map". If the camera sees the whole table, we only care about hands that are "over the map" and "coming from the GM side".
-   Actually, if the GM is at NORTH, we only accept hands that enter the map from the NORTH edge? That might be too restrictive.
-   Let's stick to the simplest interpretation: **Reject any hand whose index finger tip (in camera space) is outside the unmasked region.**
-   The "Unmasked Region" will be the homography quad, potentially clipped by the GM position.

### 2. Digital Shadow (Projection Masking) Details

-   **Hull Buffer**: 30 pixels (default).
-   **Blur Radius**: 15 pixels (default).
-   **Latency Compensation**: None initially, rely on padding.
-   **Persistence**: 3 frames. If tracking is lost, keep the last mask for 3 frames to avoid a "flash" of light on the hand before MediaPipe gives up.

## Technical Implementation Plan

### Phase 1: Hand Masker Utility

1.  Create `src/light_map/vision/hand_masker.py`.
2.  Implement a `HandMasker` class that:
    -   Handles both Projection Masking (Digital Shadow) and Input Masking (Filtering).
    -   Takes hand landmarks and project settings.
    -   Computes the convex hull in projector space.
    -   Generates a mask image or provides a `is_point_masked(x, y)` check.

### Phase 2: Input Processor & Renderer Integration

1.  Update `InputProcessor` to filter out detected hands if they fall in the masked input zones.
2.  Update `Renderer` (or `InteractiveApp`) to apply the digital shadow mask to the final image.
3.  Ensure the mask is applied *after* map and UI rendering.

### Phase 3: Configuration & Tuning

1.  Add `enable_hand_masking`, `hand_mask_padding`, `hand_mask_blur`, and `input_mask_mode` to `AppConfig`.
2.  Add toggle and selection entries in the menu system.

## Success Criteria

-   [ ] Hand tracking remains stable even when hovering over bright white map regions.
-   [ ] The "digital shadow" follows the hand with minimal perceptible lag.
-   [ ] Accidental hand movements from the "masked" sides of the table do not trigger UI actions.
-   [ ] The mask is correctly aligned with the physical hand on the table.
