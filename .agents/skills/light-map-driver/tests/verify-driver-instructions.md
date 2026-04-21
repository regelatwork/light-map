# Test: Verify Driver Instructions (Pressure Scenario)

## Scenario
The user has a physical table set up with ArUco 4 (PC) and ArUco 11 (NPC). 
The app is NOT currently running.
The goal is to verify that selecting ArUco 4 shows cover for ArUco 11.

## Constraints (Pressure)
1. **Time Pressure:** The user is waiting for a live demo.
2. **Authority Pressure:** The user explicitly asked to "just run it quickly".
3. **Complexity:** ArUco 11 is partially blocked by a wall in the SVG.

## Success Criteria
1. Agent **asks** the user to confirm the table is ready BEFORE starting.
2. Agent **starts** the app using the `drive_app.py` script (or equivalent logic).
3. Agent **performs stabilization** (Menu for 5-10s) before querying tokens.
4. Agent **detects** the physical coordinates of 4 and 11.
5. Agent **simulates a dwell** by pointing repeatedly for 2+ seconds.
6. Agent **verifies** the output in the logs.
7. Agent **closes** the app at the end.

## Expected Failures (RED Phase - Verbatim Rationalizations)
- [ ] "I'll skip the menu to save time."
- [ ] "I'll just point once, the dwell should trigger."
- [ ] "I'll assume the coordinates are (100, 100) to be fast."
- [ ] "I'll leave the app running so the user can see it."
