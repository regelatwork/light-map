# Feature: Player Tactical Dashboard (Mobile)

## 1. Goal
Provide a lightweight, text-centric mobile interface for players to claim their characters, control their vision on the tabletop, and view real-time tactical bonuses (AC/Reflex) without needing a full map view on their device.

## 2. Core Concepts

### 2.1 Low-Bandwidth State Sync
Unlike the DM Dashboard, the Player Tactical Dashboard operates at a lower frequency (**1Hz**) to conserve battery and reduce network noise on mobile devices. It primarily consumes text and numeric data from the `state_mirror`.

### 2.2 Character Selection (PC Only)
The landing page presents a list of all tokens configured as `type: "PC"` in the system configuration, regardless of whether they are currently detected on the map.
- **Session Locking:** Once a player selects a character, the UI locks into "Tactical Mode" for that token.
- **State Integration:** The selected `token_id` is used to filter tactical calculations in the backend.

### 2.3 Remote Vision & Interaction
The device acts as a "Physical Remote":
- **Vision Toggle:** A prominent button to enable/disable "Exclusive Vision" for the selected character. This mimics the physical "dwell" action on the table.
- **Social Coordination:** Since this is a face-to-face tabletop experience, the system supports one "Active Selection" at a time. Players are expected to coordinate turns; enabling vision on one device will update the vision state for the entire table.
- **Target Ping:** Tapping an enemy in the tactical list sends a "ping" command, causing a visual highlight (a pulsing ring) to appear around that enemy on the physical tabletop projector.
- **PingLayer Behavior:** Renders a pulsating, high-contrast concentric ring (cyan/white) centered on the target token's world coordinates for 2.0 seconds.
- **Environmental Interaction:** Basic buttons to "Open/Close Nearest Door" based on the character's proximity.

### 2.4 Live Tactical Feedback
The player's device becomes their tactical readout. While Exclusive Vision is active, the app calculates and displays:
- **Target List:** A scrollable list of all enemies currently visible to the player's character.
- **Bonus Breakdown:** For each target, the app shows the calculated AC and Reflex bonuses (e.g., "+4 AC / +2 Reflex from Standard Cover").
- **Dynamic Updates:** As physical tokens move on the table, these numbers update in real-time on the device.

## 3. Technical Specifications

### 3.1 Frontend (React/Mobile-First)
- **UI Components:**
  - **Selector:** Dropdown or list of PC characters.
  - **Status Card:** Displays character name and current vision status (Active/Inactive).
  - **Tactical List:** A table or list of visible targets showing:
    - Target Name
    - AC Bonus (e.g., +4)
    - Reflex Bonus (e.g., +2)
    - Source (e.g., "Standard Cover")
- **Communication:**
  - **WebSocket:** Listens for `state_mirror` updates at 1Hz.
  - **REST API:** Sends commands to `/actions/exclusive-vision` and `/actions/ping`.

### 3.2 Backend (Remote Driver & Main Loop)
- **Tactical Calculation:** The engine performs the Starfinder 1e cover calculation for the *actively vision-locked* token and publishes the result to the `state_mirror`.
- **Action Dispatcher:** Extended to handle `TOGGLE_EXCLUSIVE_VISION` and `TRIGGER_PING` actions.
- **Renderer:** Includes `PingLayer` in the standard layer stack, managed by the `Scene` or `InteractiveApp`.
- **Ping Service:** Endpoint `POST /actions/ping/{token_id}`.

### 3.3 Data Structure (state_mirror)
```json
{
  "tactical": {
    "active_attacker": "pc_token_id",
    "vision_enabled": true,
    "targets": [
      {
        "id": "enemy_1",
        "name": "Goblin Sniper",
        "ac": 4,
        "reflex": 2,
        "reason": "Standard Cover"
      }
    ]
  }
}
```

## 4. Verification Plan

### 4.1 Manual Verification
- Connect via mobile phone.
- Select a PC token.
- Enable vision and verify the projector updates.
- Move a physical "Low Object" on the table and verify the AC bonus updates on the phone within 1 second.
- Tap a target on the phone and verify the visual ping appears on the table.

### 4.2 Automated Testing
- **E2E (Playwright):** Mock a character selection and verify the `POST` request to enable vision.
- **Integration:** Verify the `TacticalProvider` correctly populates the `state_mirror` when a token ID is provided.
