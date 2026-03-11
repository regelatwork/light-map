from typing import List, Tuple, Optional, Deque
from collections import deque
import time
from dataclasses import dataclass, field
from enum import StrEnum

from light_map.common_types import MenuItem, MenuActions, GestureType
from light_map.menu_config import (
    LOCK_DELAY,
    GRACE_PERIOD,
    PRIMING_TIME,
    SUMMON_TIME,
    MAX_VISIBLE_ITEMS,
    SELECT_GESTURE,
    SUMMON_GESTURE,
    ITEM_WIDTH_PCT,
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
    item_rects: List[Tuple[int, int, int, int]]  # (x, y, w, h)
    hovered_item_index: Optional[int]
    feedback_item_index: Optional[int]  # Item to show as "Confirmed"
    prime_progress: float  # 0.0 to 1.0
    summon_progress: float  # 0.0 to 1.0
    just_triggered_action: Optional[str]
    cursor_pos: Optional[Tuple[int, int]]
    is_visible: bool
    node_stack_titles: List[str] = field(default_factory=list)
    debug_info: str = ""


class MenuSystem:
    def __init__(
        self, width: int, height: int, root_item: MenuItem, time_provider=time.monotonic
    ):
        self.width = width
        self.height = height
        self.root = root_item
        self.time_provider = time_provider

        # Navigation State
        self.current_node: MenuItem = root_item
        self.node_stack: List[MenuItem] = []  # Stack of parents
        self.page_index: int = 0

        # Interaction State
        self.state: MenuSystemState = MenuSystemState.HIDDEN
        self.summon_start_time: float = 0.0
        self.prime_start_time: float = 0.0
        self.last_selection_gesture_time: float = 0.0
        self.last_hovered_index: Optional[int] = None

        # Feedback State
        self.feedback_item_index: Optional[int] = None
        self.feedback_start_time: float = 0.0
        self.awaiting_release: bool = False

        # Input History for Pinning
        self.history: Deque[Tuple[float, int, int]] = deque(maxlen=40)
        self.pinned_cursor: Optional[Tuple[int, int]] = None
        self.is_pinning: bool = False

        self.pending_external_index: Optional[int] = None

        # Populate initial state so get_current_state() returns valid data immediately
        self._last_state: Optional[MenuState] = None
        self._last_state = self.get_current_state()

    def get_current_state(self) -> MenuState:
        """Returns the last computed state of the menu."""
        if self._last_state is None:
            # If update hasn't been called, return a default/initial state
            active_items, item_rects = self._calculate_layout()
            return MenuState(
                current_menu_title=self.current_node.title,
                active_items=active_items,
                item_rects=item_rects,
                hovered_item_index=None,
                feedback_item_index=None,
                prime_progress=0.0,
                summon_progress=0.0,
                just_triggered_action=None,
                cursor_pos=None,
                is_visible=False,
                node_stack_titles=[n.title for n in self.node_stack],
            )
        return self._last_state

    def trigger_index(self, index: int):
        """Schedules a menu item to be triggered on the next update."""
        self.pending_external_index = index

    def set_root_menu(self, new_root: MenuItem):
        # ... (rest of set_root_menu remains unchanged)

        # If hidden, just reset completely
        if self.state == MenuSystemState.HIDDEN:
            self.root = new_root
            self.current_node = self.root
            self.node_stack.clear()
            self.page_index = 0
            return

        # If active, attempt to preserve position by traversing the new tree
        # 1. Capture current path (titles)
        path_titles = [n.title for n in self.node_stack]
        path_titles.append(self.current_node.title)

        # 2. Traverse new tree
        self.root = new_root

        new_node_stack: List[MenuItem] = []
        curr = new_root

        # Verify root matches first item in path
        if not path_titles or new_root.title != path_titles[0]:
            # Root mismatch or empty path, fallback to reset
            self.current_node = self.root
            self.node_stack.clear()
            self.page_index = 0
            return

        # Traverse the rest of the path
        match_success = True
        for title in path_titles[1:]:
            found_child = None
            for child in curr.children:
                if child.title == title:
                    found_child = child
                    break

            if found_child:
                new_node_stack.append(curr)
                curr = found_child
            else:
                match_success = False
                break

        if match_success:
            self.node_stack = new_node_stack
            self.current_node = curr
            # We keep page_index, but should clamp it just in case
            # For simplicity, we can reset it or keep it. resetting is safer for dynamic lists.
            # But for a toggle, keeping it is better UX.
            # self.page_index = 0
        else:
            # Fallback to root if path lost
            self.current_node = self.root
            self.node_stack.clear()
            self.page_index = 0

    def update(self, x: int, y: int, gesture: GestureType) -> MenuState:
        now = self.time_provider()

        # 1. Clamp Input
        cx = max(0, min(x, self.width))
        cy = max(0, min(y, self.height))

        # 2. Update History
        self.history.append((now, cx, cy))

        # 3. State Machine
        just_triggered_action = None

        if self.pending_external_index is not None:
            if self.state in [
                MenuSystemState.ACTIVE,
                MenuSystemState.WAITING_FOR_NEUTRAL,
            ]:
                self.last_hovered_index = self.pending_external_index
                triggering_index = self.last_hovered_index
                just_triggered_action = self._trigger_selection()

                # If we didn't just hide the menu, show feedback
                if self.state != MenuSystemState.HIDDEN:
                    self.feedback_item_index = triggering_index
                    self.feedback_start_time = now
                else:
                    # Even if hidden, we might want the returned state to show it once
                    # but _reset_to_hidden cleared it. For now, let's just let it be None if hidden.
                    pass
            self.pending_external_index = None

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

        elif self.state == MenuSystemState.WAITING_FOR_NEUTRAL:
            if gesture == GestureType.OPEN_PALM or (
                gesture != SUMMON_GESTURE and gesture != SELECT_GESTURE
            ):
                self.state = MenuSystemState.ACTIVE

        elif self.state == MenuSystemState.ACTIVE:
            pass

        # 4. Cursor Pinning Logic
        active_cursor = (cx, cy)

        # Check for release
        if self.awaiting_release:
            if gesture != SELECT_GESTURE:
                self.awaiting_release = False

        # Feedback Timer
        if self.feedback_item_index is not None:
            if now - self.feedback_start_time > 0.5:
                self.feedback_item_index = None

        if self.state == MenuSystemState.ACTIVE:
            if gesture == SELECT_GESTURE and not self.awaiting_release:
                if not self.is_pinning:
                    target_time = now - LOCK_DELAY
                    best_pt = (cx, cy)
                    for t, hx, hy in reversed(self.history):
                        if t <= target_time:
                            best_pt = (hx, hy)
                            break
                    self.pinned_cursor = best_pt
                    self.is_pinning = True
                    self.prime_start_time = now

                if self.pinned_cursor:
                    active_cursor = self.pinned_cursor

                if now - self.prime_start_time >= PRIMING_TIME:
                    # Capture triggering item index BEFORE resetting
                    # trigger_selection returns action ID, but we need the index for feedback
                    # We can get it from last_hovered_index (sticky selection)
                    triggering_index = self.last_hovered_index

                    just_triggered_action = self._trigger_selection()

                    if just_triggered_action:
                        self.awaiting_release = True
                        self.feedback_item_index = triggering_index
                        self.feedback_start_time = now

                    self.prime_start_time = now
                    self.is_pinning = False
                    self.pinned_cursor = None
                    if just_triggered_action == MenuActions.EXIT:
                        self._reset_to_hidden()
            else:
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
        current_hovered_index = None

        if self.state == MenuSystemState.ACTIVE:
            cursor_x, cursor_y = active_cursor
            for i, (rx, ry, rw, rh) in enumerate(item_rects):
                if rx <= cursor_x <= rx + rw and ry <= cursor_y <= ry + rh:
                    current_hovered_index = i
                    break

            # Sticky Logic: Only update if we are hovering a NEW item.
            # If we drift off, keep the old one.
            if current_hovered_index is not None:
                self.last_hovered_index = current_hovered_index
        else:
            self.last_hovered_index = None

        # 6. Construct State DTO
        summon_prog = 0.0
        if self.state == MenuSystemState.HIDDEN and self.summon_start_time > 0:
            summon_prog = min(1.0, (now - self.summon_start_time) / SUMMON_TIME)

        prime_prog = 0.0
        if self.state == MenuSystemState.ACTIVE and self.is_pinning:
            prime_prog = min(1.0, (now - self.prime_start_time) / PRIMING_TIME)

        self._last_state = MenuState(
            current_menu_title=self.current_node.title,
            active_items=active_items,
            item_rects=item_rects,
            hovered_item_index=self.last_hovered_index,
            feedback_item_index=self.feedback_item_index,
            prime_progress=prime_prog,
            summon_progress=summon_prog,
            just_triggered_action=just_triggered_action,
            cursor_pos=active_cursor if self.state == MenuSystemState.ACTIVE else None,
            is_visible=(self.state != MenuSystemState.HIDDEN),
            node_stack_titles=[n.title for n in self.node_stack],
            debug_info=f"State: {self.state}",
        )
        return self._last_state

    def _calculate_layout(
        self,
    ) -> Tuple[List[MenuItem], List[Tuple[int, int, int, int]]]:
        all_items = []
        if self.node_stack:
            back_item = MenuItem(title="< Back", action_id=MenuActions.NAV_BACK)
            all_items.append(back_item)

        all_items.extend(self.current_node.children)

        total_items = len(all_items)
        max_per_page = MAX_VISIBLE_ITEMS
        display_items = []

        if total_items <= max_per_page:
            display_items = all_items
        else:
            has_prev = self.page_index > 0
            page_size = max_per_page - 2
            start = self.page_index * page_size
            end = start + page_size
            chunk = all_items[start:end]

            if has_prev:
                display_items.append(
                    MenuItem(
                        title="< Prev Page",
                        action_id=MenuActions.PAGE_PREV,
                        should_close_on_trigger=False,
                    )
                )
            display_items.extend(chunk)
            if total_items > end:
                display_items.append(
                    MenuItem(
                        title="Next Page >",
                        action_id=MenuActions.PAGE_NEXT,
                        should_close_on_trigger=False,
                    )
                )

        count = len(display_items)
        if count == 0:
            return [], []

        box_height = 80
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
        active_items, _ = self._calculate_layout()

        # Use sticky selection index instead of cursor hit testing
        if self.last_hovered_index is None:
            return None

        if self.last_hovered_index >= len(active_items):
            return None

        selected_item = active_items[self.last_hovered_index]

        if selected_item.action_id == MenuActions.NAV_BACK:
            if self.node_stack:
                self.current_node = self.node_stack.pop()
                self.page_index = 0
                self.last_hovered_index = None  # Reset selection on nav
            return None

        if selected_item.action_id == MenuActions.PAGE_NEXT:
            self.page_index += 1
            self.last_hovered_index = None
            return None

        if selected_item.action_id == MenuActions.PAGE_PREV:
            self.page_index = max(0, self.page_index - 1)
            self.last_hovered_index = None
            return None

        if selected_item.children:
            self.node_stack.append(self.current_node)
            self.current_node = selected_item
            self.page_index = 0
            self.last_hovered_index = None
            return None

        if selected_item.should_close_on_trigger:
            self._reset_to_hidden()

        return selected_item.action_id

    def _reset_to_hidden(self):
        self.state = MenuSystemState.HIDDEN
        self.current_node = self.root
        self.node_stack.clear()
        self.page_index = 0
        self.summon_start_time = 0
        self.prime_start_time = 0
        self.is_pinning = False
        self.pinned_cursor = None
        self.last_hovered_index = None
        self.awaiting_release = False
        self.feedback_item_index = None
        self.feedback_start_time = 0.0
