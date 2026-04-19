# Tactical Cover and Reflex Bonuses (Starfinder 1e)

## 1. Goal
Automatically calculate and display Armor Class (AC) and Reflex save bonuses provided by "Low Objects" (cover) during Exclusive Vision. This automates the Starfinder 1e corner-to-corner cover rules using a high-resolution, pixel-based approach.

## 2. Core Concepts

### 2.1 Low Objects
"Low Objects" are obstacles that are approximately half-height (e.g., crates, low walls). They provide cover but do not necessarily block line-of-sight entirely.
- **Extraction:** Detected via SVG layers containing both "low" and "object" (case-insensitive).
- **Representation:** Stored in the `blocker_mask` with a dedicated value (`MASK_VALUE_LOW = 50`).

### 2.2 Starfinder 1e Cover Rules
The engine implements the following rules for calculating cover:
- **Obstacle Proximity:** A low object only provides cover if the target is within 30 feet (6 grid squares) of the obstacle and closer to the obstacle than the attacker is.
- **Best Vantage:** The attacker (PC) chooses their "best corner" (any pixel on their footprint boundary) to see as much of the target (NPC) as possible.
- **Cover Grades:**
  - **No Cover:** 0% of the target's boundary pixels are obscured.
  - **Partial Cover (+2 AC, +1 Reflex):** > 0% but < 50% of target boundary pixels obscured.
  - **Standard Cover (+4 AC, +2 Reflex):** > 50% but < 90% of target boundary pixels obscured.
  - **Improved Cover (+8 AC, +4 Reflex):** > 90% of target boundary pixels obscured.
  - **Total Cover:** No attacker pixel can see any target pixel (No LOS).

## 3. Technical Specifications

### 3.1 Numba-Optimized $N^2$ Algorithm
For each visible NPC token during Exclusive Vision:
1. Extract boundary pixels for both Attacker (PC) and Target (NPC).
2. For each Target pixel, check if it is "visible" from **any** Attacker pixel.
3. A line is **obscured** if it intersects a `LOW_OBJECT` and satisfies the 30ft/proximity conditions.
4. A line is **blocked** if it intersects a `WALL` or `CLOSED_DOOR`.

### 3.2 Tactical Overlay
- **Floating Labels:** A dedicated rendering layer (`TacticalOverlayLayer`) displays cover bonuses below the name of each visible target token.
- **GM Mode:** GMs can enter Exclusive Vision for an NPC to see cover bonuses against all PCs.
- **Manual Overrides:** Frontend toggles allow the GM to manually set cover or concealment states for any token, overriding the geometric calculation.

## 4. Success Criteria
- **Accuracy:** Cover bonuses match Starfinder 1e rules for distance and proximity.
- **Performance:** $N^2$ calculations for visible tokens remain performant (sub-16ms) via Numba optimization.
- **Clarity:** Floating labels provide immediate tactical feedback during "searchlight" inspection.
