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

### 2.3 Soft Cover (Creatures)
Creatures (allies or enemies) provide "Soft Cover" if they stand between the attacker and the target.
- **Bonuses:** Soft cover provides a **+4 AC bonus** but **no bonus to Reflex saves** (+0 Reflex).
- **Mutual Exclusion:** Creatures sharing the same space (e.g., Tiny creatures in a Medium space) do not provide cover to each other.
- **Precedence:** Soft cover does not stack with other forms of cover. If a target has both soft cover and partial cover, the higher AC bonus (+4) applies, but the Reflex bonus remains (+1) from the partial cover.

## 3. Technical Specifications

### 3.1 Numba-Optimized "Stamp & Trace" Algorithm
For each visible NPC token during Exclusive Vision, the engine performs a dynamic "Stamp & Trace" calculation:
1. **Extract Boundaries:** Get boundary pixels for both Attacker (PC) and Target (NPC).
2. **Stamp Mask:** 
   - Create a temporary copy of the static `blocker_mask`.
   - Stamp the footprints of all active tokens (excluding attacker and target) as `MASK_VALUE_SOFT_COVER = 75`.
3. **Trace Rays:** For each Target pixel, check if it is "visible" from **any** Attacker pixel using the stamped mask.
4. **Determine Status:**
   - A line is **obscured** if it intersects a `LOW_OBJECT` (val 50) and satisfies proximity conditions.
   - A line is **blocked** if it intersects a `WALL` (val 255), `CLOSED_DOOR` (val 200), or `TALL_OBJECT` (val 100).
   - A line has **soft cover** if it intersects a creature (val 75) without hitting a harder obstacle.
5. **Aggregate Grades:** The final cover grade is determined by the percentage of obscured vs. soft-cover lines. Harder cover always takes precedence for a given ray.

### 3.2 Tactical Overlay
- **Floating Labels:** A dedicated rendering layer (`TacticalOverlayLayer`) displays cover bonuses below the name of each visible target token.
- **Cone of Fire:** For each visible target, a visual "cone" radiates from the attacker's best vantage point (apex) to the target's near-side boundary.
  - **Discrete Wedges:** If objects or walls block part of the view, the cone is split into multiple discrete wedges.
  - **Status Textures:**
    - **Clear LOS:** Solid translucent fill (low alpha).
    - **Low Cover:** "Tactical Radar" stipple pattern (sparse dot grid).
  - **Sharp Edges:** White lines define the outer boundaries of each visible wedge.
- **GM Mode:** GMs can enter Exclusive Vision for an NPC to see cover bonuses against all PCs.
- **Manual Overrides:** Frontend toggles allow the GM to manually set cover or concealment states for any token, overriding the geometric calculation.

## 4. Success Criteria
- **Accuracy:** Cover bonuses match Starfinder 1e rules for distance and proximity.
- **Performance:** $N^2$ calculations for visible tokens remain performant (sub-16ms) via Numba optimization.
- **Clarity:** Floating labels provide immediate tactical feedback during "searchlight" inspection.
