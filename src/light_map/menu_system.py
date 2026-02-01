from typing import List, Tuple, Optional, Deque, Dict
from collections import deque
import time
from dataclasses import dataclass
from enum import StrEnum

from src.light_map.common_types import MenuItem, MenuActions, GestureType
from src.light_map.menu_config import (
    LOCK_DELAY, GRACE_PERIOD, PRIMING_TIME, SUMMON_TIME,
    MAX_VISIBLE_ITEMS, SELECT_GESTURE, SUMMON_GESTURE, ITEM_WIDTH_PCT
)

class MenuSystemState(StrEnum):
    HIDDEN = "HIDDEN"
    SUMMONING = "SUMMONING"
    WAITING_FOR_NEUTRAL = "WAITING_FOR_NEUTRAL"
    ACTIVE = "ACTIVE"

@dataclass
class MenuState:
    current_menu_title: str
    active_items: List[MenuItem]
    item_rects: List[Tuple[int, int, int, int]] # (x, y, w, h)
    hovered_item_index: Optional[int]
    prime_progress: float # 0.0 to 1.0
    summon_progress: float # 0.0 to 1.0
    just_triggered_action: Optional[str]
    cursor_pos: Optional[Tuple[int, int]]
    is_visible: bool
    debug_info: str = ""

class MenuSystem:
    def __init__(self, width: int, height: int, root_item: MenuItem, time_provider=time.monotonic):
        self.width = width
        self.height = height
        self.root = root_item
        self.time_provider = time_provider

        # Navigation State
        self.current_node: MenuItem = root_item
        self.node_stack: List[MenuItem] = [] # Stack of parents

        # Interaction State
        self.state: MenuSystemState = MenuSystemState.HIDDEN
        self.summon_start_time: float = 0.0
        self.prime_start_time: float = 0.0
        self.last_selection_gesture_time: float = 0.0
        
        # Input History for Pinning
        # Assume 60 FPS roughly for buffer size. 
        # maxlen = FPS * LOCK_DELAY * 2 (safety factor)
        # 60 * 0.3 * 2 = 36 -> 40
        self.history: Deque[Tuple[float, int, int]] = deque(maxlen=40)
        self.pinned_cursor: Optional[Tuple[int, int]] = None
        self.is_pinning: bool = False

    def update(self, x: int, y: int, gesture: GestureType) -> MenuState:
        now = self.time_provider()
        
        # 1. Clamp Input
        cx = max(0, min(x, self.width))
        cy = max(0, min(y, self.height))

        # 2. Update History
        self.history.append((now, cx, cy))

        # 3. State Machine
        just_triggered_action = None
        
        if self.state == MenuSystemState.HIDDEN:
            if gesture == SUMMON_GESTURE:
                if self.summon_start_time == 0:
                    self.summon_start_time = now
                
                elapsed = now - self.summon_start_time
                if elapsed >= SUMMON_TIME:
                    self.state = MenuSystemState.WAITING_FOR_NEUTRAL
                    self.summon_start_time = 0
            else:
                self.summon_start_time = 0

        elif self.state == MenuSystemState.SUMMONING:
            # Transitional state logic handled inside HIDDEN check usually,
            # but here we treat HIDDEN as the resting state and SUMMONING as implied 
            # by the timer. 
            # Actually, let's keep it simple. If we are HIDDEN and detecting, we are technically summoning.
            # But to expose state to renderer, we might want to distinguish?
            # For this implementation, HIDDEN covers "Hidden" and "Summoning process".
            # The 'summon_progress' in DTO covers the visual feedback.
            pass

        elif self.state == MenuSystemState.WAITING_FOR_NEUTRAL:
            # Must release the summon gesture/fist before menu becomes interactive
            # to prevent accidental clicks
            if gesture == GestureType.OPEN_PALM or (gesture != SUMMON_GESTURE and gesture != SELECT_GESTURE):
                self.state = MenuSystemState.ACTIVE
        
        elif self.state == MenuSystemState.ACTIVE:
            # Check for Exit/Dismissal
            # If user does "Open Palm" for a long time? Or maybe specific close gesture?
            # For now, explicit "Exit" button or holding Victory again to toggle?
            # Design doc doesn't specify "Quick Close" gesture, only MenuActions.EXIT.
            pass

        # 4. Cursor Pinning Logic (Only relevant if Active)
        active_cursor = (cx, cy)
        
        if self.state == MenuSystemState.ACTIVE:
            if gesture == SELECT_GESTURE:
                # If we just started pinning or lost it briefly
                if not self.is_pinning:
                    # Look back in history for position at (now - LOCK_DELAY)
                    target_time = now - LOCK_DELAY
                    best_pt = (cx, cy)
                    # Search backwards
                    for t, hx, hy in reversed(self.history):
                        if t <= target_time:
                            best_pt = (hx, hy)
                            break
                    self.pinned_cursor = best_pt
                    self.is_pinning = True
                    self.prime_start_time = now # Start priming
                
                # Use pinned cursor
                if self.pinned_cursor:
                    active_cursor = self.pinned_cursor
                
                # Check Priming
                if now - self.prime_start_time >= PRIMING_TIME:
                    # TRIGGER!
                    just_triggered_action = self._trigger_selection()
                    
                    # Reset after trigger
                    self.prime_start_time = now 
                    self.is_pinning = False # Unlock to allow repeated clicks or visual feedback
                    self.pinned_cursor = None
                    
                    # If action closes menu
                    if just_triggered_action == MenuActions.EXIT: # Or check current item config
                        self._reset_to_hidden()
            
            else:
                # Not selecting
                # Debounce/Grace Period check
                # If we lost selection gesture, do we immediately reset?
                # Using GRACE_PERIOD to allow brief flickers is complex for pinning reset.
                # For simplicity: If gesture is NOT Select, we reset pinning immediately 
                # unless we want to implement the specific debounce logic.
                # Doc says: "If SELECT_GESTURE is lost... wait GRACE_PERIOD... before resetting prime timer"
                
                if self.is_pinning:
                    if now - self.last_selection_gesture_time > GRACE_PERIOD:
                        self.is_pinning = False
                        self.pinned_cursor = None
                        self.prime_start_time = 0
                else:
                    self.prime_start_time = 0

            if gesture == SELECT_GESTURE:
                self.last_selection_gesture_time = now

        # 5. Layout & Hit Testing
        active_items, item_rects = self._calculate_layout()
        hovered_index = None
        
        if self.state == MenuSystemState.ACTIVE:
            # Check collision with active_cursor
            cursor_x, cursor_y = active_cursor
            for i, (rx, ry, rw, rh) in enumerate(item_rects):
                if rx <= cursor_x <= rx + rw and ry <= cursor_y <= ry + rh:
                    hovered_index = i
                    break
        
        # 6. Construct State DTO
        
        # Calculate Progress
        summon_prog = 0.0
        if self.state == MenuSystemState.HIDDEN and self.summon_start_time > 0:
            summon_prog = min(1.0, (now - self.summon_start_time) / SUMMON_TIME)
        
        prime_prog = 0.0
        if self.state == MenuSystemState.ACTIVE and self.is_pinning:
            prime_prog = min(1.0, (now - self.prime_start_time) / PRIMING_TIME)

        return MenuState(
            current_menu_title=self.current_node.title,
            active_items=active_items,
            item_rects=item_rects,
            hovered_item_index=hovered_index,
            prime_progress=prime_prog,
            summon_progress=summon_prog,
            just_triggered_action=just_triggered_action,
            cursor_pos=active_cursor if self.state == MenuSystemState.ACTIVE else None,
            is_visible=(self.state != MenuSystemState.HIDDEN),
            debug_info=f"State: {self.state}"
        )

    def _calculate_layout(self) -> Tuple[List[MenuItem], List[Tuple[int, int, int, int]]]:
        # 1. Prepare Item List
        # Always inject "Back" if we have a parent
        display_items = []
        if self.node_stack:
            back_item = MenuItem(title="< Back", action_id=MenuActions.NAV_BACK)
            display_items.append(back_item)
        
        display_items.extend(self.current_node.children)

        # 2. Handle Overflow
        # If > MAX_VISIBLE, slice and add "..."
        if len(display_items) > MAX_VISIBLE_ITEMS:
            display_items = display_items[:MAX_VISIBLE_ITEMS - 1]
            display_items.append(MenuItem(title="...", action_id=None))

        # 3. Calculate Geometry
        # Center vertically
        # Center horizontally
        
        count = len(display_items)
        if count == 0:
            return [], []

        # Constants
        box_height = 80 # px, could be config
        gap = 20
        total_menu_height = (count * box_height) + ((count - 1) * gap)
        
        start_y = (self.height - total_menu_height) // 2
        
        box_width = int(self.width * ITEM_WIDTH_PCT)
        start_x = (self.width - box_width) // 2
        
        rects = []
        current_y = start_y
        for _ in display_items:
            rects.append((start_x, current_y, box_width, box_height))
            current_y += box_height + gap
            
        return display_items, rects

    def _trigger_selection(self) -> Optional[str]:
        # Identify what is hovered
        active_items, item_rects = self._calculate_layout()
        
        # Use pinned cursor (we are in trigger moment)
        if not self.pinned_cursor:
            print("Trigger failed: No pinned cursor")
            return None
            
        cx, cy = self.pinned_cursor
        
        selected_item = None
        for i, (rx, ry, rw, rh) in enumerate(item_rects):
            if rx <= cx <= rx + rw and ry <= cy <= ry + rh:
                selected_item = active_items[i]
                break
        
        if not selected_item:
            print(f"Trigger failed: No collision at {cx}, {cy}. Rects: {item_rects}")
            return None
            
        # Handle Navigation
        if selected_item.action_id == MenuActions.NAV_BACK:
            if self.node_stack:
                self.current_node = self.node_stack.pop()
            return None # Internal action, not emitted to app? 
                        # Or emit NAV_BACK if app needs to know? 
                        # Usually internal.
        
        # Handle Submenu
        if selected_item.children:
            self.node_stack.append(self.current_node)
            self.current_node = selected_item
            return None
        
        # Handle Leaf Action
        if selected_item.should_close_on_trigger:
            self._reset_to_hidden()
            
        return selected_item.action_id

    def _reset_to_hidden(self):
        self.state = MenuSystemState.HIDDEN
        self.current_node = self.root # Reset to root? Or keep state?
        # Usually menus reset to root on close
        self.node_stack.clear()
        self.summon_start_time = 0
        self.prime_start_time = 0
        self.is_pinning = False
        self.pinned_cursor = None
