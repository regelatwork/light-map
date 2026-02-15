# Feature: Projection Interference Mitigation

## Problem

Projecting on a surface creates intense light that washes out hand features, causing MediaPipe tracking to fail. The camera sees a white blob instead of a hand. Additionally, the colored light from the projector (e.g., a blue ocean on the map) tints the hand, confusing the skin-tone based models in MediaPipe.

## Goals

Improve hand tracking robustness *without* degrading the visual quality of the projection (e.g., dimming) unless absolutely necessary.

## History & Lessons Learned

### Attempt 1: Computer Vision Enhancement (Gamma/CLAHE) [REVERTED]

- **Concept**: Modify the camera input frame with Gamma Correction and CLAHE to recover details.
- **Result**: **Failed**. Amplified noise; intense light still saturated sensor.
- **Status**: Codebase reverted in Feb 2026.

### Attempt 2: Channel Isolation (Red/Green/Blue) [REVERTED]

- **Concept**: Process only a single color channel (e.g., Red).
- **Result**: **Failed**. Saturation persisted; MediaPipe needs full RGB for skin segmentation.
- **Status**: Codebase reverted in Feb 2026.

### Attempt 3: Static Background Subtraction [REVERTED]

- **Concept**: Mathematically subtract the static map projection from the camera feed.
- **Result**: **Failed**. While it isolated the hand *shape* from the background, the *texture* of the hand (RGB color) was still corrupted by the projected light. MediaPipe relies heavily on skin texture/color, not just silhouette. Additionally, sharp color transitions in the menu further confused detection.
- **Status**: Codebase reverted in Feb 2026.

### Attempt 4: UI-Based Interference Mitigation (Dimming) [PARTIAL SUCCESS]

- **Concept**: Hide the map when the menu is active; dim the map during interactions.
- **Result**: **Good**. Menu interaction is much cleaner.
- **Issue**: The *Highlight* on the selected menu item (filling the button with color) still throws off tracking. Also, closing the hand to select shifts the tracking point, causing accidental deselection.

______________________________________________________________________

## Current Strategy: Sticky Selection & Minimalist UI

To further improve menu robustness, we need to minimize the visual change on the hand itself (avoid projecting color onto it) and decouple the selection mechanic from precise fingertip stability.

### Proposed Solution: Sticky Selection with Perimeter Highlight

#### 1. Sticky Selection Logic

- **Current Behavior**: Selection follows the cursor strictly. If the cursor leaves the item (e.g., due to hand closing shifting the landmark), the item is deselected.
- **New Behavior**: The last validly hovered item remains "Active/Selected" until the cursor actively enters a *different* item.
  - **Benefit**: Users can hover, then close their hand comfortably without worrying about micro-movements deselecting the target. The cursor can even leave the menu area entirely, and the last item remains primed for activation.

#### 2. Perimeter Highlight (Visuals)

- **Current Behavior**: Hovered items are filled with a solid color. This projects bright light onto the hand, confusing the camera.
- **New Behavior**:
  - **No Fill**: Keep the button background black (or very dark).
  - **Thick Border**: Draw a thick, high-contrast colored border (e.g., Green or Cyan) around the selected item.
  - **Text Change**: Optionally change text color or size.
  - **Benefit**: The inside of the button (where the hand is) remains dark. The projector does not illuminate the hand, preserving tracking accuracy.

### Implementation Details (Completed Feb 2026)

1. **Updated `MenuSystem` Logic**:

   - Modified `update()` to implement **Sticky Selection**. `last_hovered_index` persists the selection even if the cursor drifts into empty space.
   - Selection is only changed when the cursor actively enters a *new* item.

1. **Updated `Renderer` Visuals**:

   - Removed solid fill for hovered items.
   - Implemented **Thick Perimeter Border** (high contrast) for selection.
   - Result: Hand remains in darkness (black background), significantly improving tracking reliability during the critical "close fist" gesture.

1. **Menu Isolation**:

   - The map layer is now hidden (Opacity 0.0) whenever the menu is active, ensuring maximum contrast and zero interference from map colors.

1. **Interactive Dimming**:

   - The map layer is dimmed (Opacity 0.5) during Pan/Zoom operations to reduce glare while maintaining usability.
