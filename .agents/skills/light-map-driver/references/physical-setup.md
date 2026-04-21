# Physical Table Setup & Verification

Use this guide when the user has a physical table with ArUco tokens and a projector.

## User Request Pattern
Before starting the automation, ensure the user has the table ready.
**Prompt:** "Please ensure the physical map is on the table and tokens (e.g., PC 4, NPCs 11 and 12) are placed in their tactical positions. I will now start the automation to verify the logic."

## Detection Stabilization Workflow
Physical tokens can be hard to detect if the projector is throwing a bright white light on them.
1. **Initial Wait:** Wait 5-10 seconds for the application and camera pipeline to initialize.
2. **Menu Trigger:** Open the `TRIGGER_MENU` (Action). This provides a dark background which significantly improves ArUco contrast for the camera.
3. **Stabilization Time:** Keep the menu open for at least 5-10 seconds.
4. **Coordinate Query:** Use `GET /state/tokens` to find the actual `world_x, world_y` of the physical tokens.
5. **Dynamic Pointing:** Point at the *detected* coordinates, not hardcoded ones.

## Observation Guidelines
Inform the user what to look for:
- "The menu should open for a few seconds to stabilize detection."
- "You should see the selection progress circle (dwell) on Token X."
- "The searchlight should appear, and tactical labels should show below the tokens."
