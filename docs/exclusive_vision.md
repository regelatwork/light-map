# Exclusive Vision Mode

Exclusive Vision is a powerful tactical feature that allows players or Game Masters to visualize the precise **Line-of-Sight (LOS)** from a specific token's perspective. It transforms the tabletop into a focused "searchlight" view, blacking out everything the chosen token cannot see.

______________________________________________________________________

## 1. How to Trigger

Exclusive Vision is activated using a **Pointing Dwell Interaction** while in **Viewing Mode**.

1. **Gesture**: Perform the **Pointing** gesture (index finger extended) with one hand.
1. **Target**: Aim the virtual pointer (extending ~1 inch from your finger tip) at a physical or digital token on the map.
1. **Dwell**: Maintain the point for **2 seconds**.
1. **Activation**: The system will trigger the mode, providing immediate visual and textual feedback.

______________________________________________________________________

## 2. Real-Time Behavior

Once activated, the system enters a specialized rendering state:

- **Notification**: A notification appears at the top of the screen: `Inspecting: [Token Name]`.
- **Searchlight Effect**: The map is rendered at **Full Brightness** within the token's LOS, while all areas outside its vision are covered by a **Solid Black Mask** (`ALPHA_OPAQUE`).
- **Door Interactions**: If the token's LOS is blocked by a "Closed Door" in the SVG map, opening that door (via the menu or other interactions) will dynamically update the LOS mask in real-time.
- **Dynamic Masking**: As the physical token is moved, the LOS mask is recalculated and re-projected instantly, allowing for "dynamic scouting".

______________________________________________________________________

## 3. Inspection Linger

To prevent the vision from flickering or disappearing if you briefly drop your hand, the system employs an **Inspection Linger** timer.

- **Duration**: By default, the Exclusive Vision remains active for **10 seconds** after you stop pointing at the token.
- **Persistence**: You can move your hand away, change gestures, or even point at something else, and the vision will persist until the timer expires.
- **Reset**: Pointing at the *same* token again resets the linger timer. Pointing at a *different* token for 2 seconds will immediately switch the inspection to that new token.
- **Manual Clear**: You can clear the inspection immediately by performing a **Victory** gesture to open the menu, or by waiting for the timer to expire.

______________________________________________________________________

## 4. Visual Cues Summary

| Feature | Behavior in Exclusive Vision | Normal Viewing Mode |
| :--- | :--- | :--- |
| **Map Brightness** | **Full (1.0)** within LOS | Full (1.0) |
| **Fog of War** | **Total Darkness (Black)** outside LOS | **Dimmed (Shroud)** for explored areas |
| **Notifications** | `Inspecting: [Name]` | None (unless toggling tokens) |
| **Tokens** | Only the inspected token and those in its LOS are highlighted | All visible tokens are shown |
| **Doors** | Highlights relevant doors in the token's path | Shows all doors |

______________________________________________________________________

## 5. Configuration

You can adjust the behavior of Exclusive Vision in `map_state.json` or via the global configuration:

- `inspection_linger_duration`: The time (in seconds) the vision remains active after the gesture ends (Default: `10.0`).
- `pointer_extension_inches`: The distance the virtual cursor extends beyond the fingertip for easier targeting (Default: `1.0`).
