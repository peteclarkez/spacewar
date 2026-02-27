"""
Xbox-style gamepad support — up to 2 controllers.

Axis / button indices are verified for a standard Xbox controller.
Adjust the BTN_* / AXIS_* constants at the top if your hardware differs.
Player 1 → joystick index 0 (Enterprise).
Player 2 → joystick index 1 (Klingon).
"""

from __future__ import annotations
import pygame

# ── Button indices ────────────────────────────────────────────────────────────
BTN_A        = 0    # Fire phasers
BTN_B        = 1    # Cloak
BTN_X        = 3    # Fire torpedo
BTN_Y        = 4    # Hyperspace
BTN_LB       = 6    # Hyperspace (alt)
BTN_RB       = 7    # Fire torpedo (alt)
BTN_SELECT   = 10   # Attract / exit
BTN_START    = 11   # Start game / Pause
BTN_RSTICK   = 14   # Toggle own robot AI

# ── Axis indices ──────────────────────────────────────────────────────────────
AXIS_LSTICK_X  = 0   # Left/right → rotate
AXIS_LTRIGGER  = 5   # Thrust  (rest≈0, pressed→+1)
AXIS_RSTICK_X  = 2   # Right stick X (energy balance)
AXIS_RTRIGGER  = 4   # Fire phasers alt (rest≈0, pressed→-1  INVERTED)

# ── Thresholds ────────────────────────────────────────────────────────────────
AXIS_DEAD_ZONE = 0.25
TRIGGER_THRESH = 0.5


class JoystickState:
    """
    Snapshot of one gamepad's state for a single tick.
    Derived from events + current axis values.
    """
    __slots__ = (
        "rotate_left", "rotate_right", "thrust", "cloak",
        "phaser", "torpedo", "hyperspace",
        "shield_to_energy", "energy_to_shield",
        "start_pressed", "select_pressed", "rstick_click",
        "dpad_up", "dpad_down",
    )

    def __init__(self) -> None:
        for s in self.__slots__:
            setattr(self, s, False)


class JoystickManager:
    """Manages up to 2 joysticks and translates their input into actions."""

    def __init__(self) -> None:
        self._joysticks: list[pygame.joystick.JoystickType | None] = [None, None]
        self._prev_buttons: list[set[int]] = [set(), set()]
        self.states: list[JoystickState] = [JoystickState(), JoystickState()]

    def init(self) -> None:
        """Initialise all connected joysticks (call after pygame.init)."""
        if not pygame.get_init():
            return
        for i in range(min(2, pygame.joystick.get_count())):
            joy = pygame.joystick.Joystick(i)
            joy.init()
            self._joysticks[i] = joy

    def update(self) -> None:
        """Poll joystick state and populate self.states[0] and self.states[1]."""
        for idx, joy in enumerate(self._joysticks):
            st = JoystickState()
            self.states[idx] = st
            if joy is None:
                continue

            # --- Axes ---
            def ax(n: int) -> float:
                try:
                    return joy.get_axis(n)
                except Exception:
                    return 0.0

            lx = ax(AXIS_LSTICK_X)
            if lx < -AXIS_DEAD_ZONE:
                st.rotate_left = True
            elif lx > AXIS_DEAD_ZONE:
                st.rotate_right = True

            if ax(AXIS_LTRIGGER) > TRIGGER_THRESH:
                st.thrust = True

            rx = ax(AXIS_RSTICK_X)
            if rx < -AXIS_DEAD_ZONE:
                st.shield_to_energy = True
            elif rx > AXIS_DEAD_ZONE:
                st.energy_to_shield = True

            if ax(AXIS_RTRIGGER) < -TRIGGER_THRESH:
                st.phaser = True

            # --- Buttons (edge-triggered) ---
            def btn(n: int) -> bool:
                try:
                    return bool(joy.get_button(n))
                except Exception:
                    return False

            cur_buttons = {b for b in range(joy.get_numbuttons()) if btn(b)}
            prev = self._prev_buttons[idx]
            newly_pressed = cur_buttons - prev
            self._prev_buttons[idx] = cur_buttons

            if BTN_A in cur_buttons or BTN_RB in cur_buttons:
                st.phaser = True
            if BTN_B in cur_buttons:
                st.cloak = True
            if BTN_X in cur_buttons or BTN_RB in cur_buttons:
                st.torpedo = True
            if BTN_Y in newly_pressed or BTN_LB in newly_pressed:
                st.hyperspace = True

            if BTN_START in newly_pressed:
                st.start_pressed = True
            if BTN_SELECT in newly_pressed:
                st.select_pressed = True
            if BTN_RSTICK in newly_pressed:
                st.rstick_click = True

            # D-pad (hat 0)
            try:
                hat = joy.get_hat(0)
                st.dpad_up   = hat[1] > 0
                st.dpad_down = hat[1] < 0
            except Exception:
                pass
