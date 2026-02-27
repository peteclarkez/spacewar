"""joystick.py — Xbox-style gamepad input.

Player 1 → joystick index 0  (Enterprise)
Player 2 → joystick index 1  (Klingon, if a second controller is connected)

Button mapping (verified against controller_test.py output):
  Btn  0 (A)       → Fire phasers           (keyboard: Q / KP7)  [edge-triggered]
  Btn  1 (B)       → Cloak                  (keyboard: W / KP8)  [held]
  Btn  3 (X)       → Fire photon torpedo    (keyboard: E / KP9)  [held]  (also RB)
  Btn  4 (Y)       → Hyperspace             (keyboard: X / KP2)  [edge-triggered]  (also LB)
  Btn  6 (LB)      → Hyperspace             (keyboard: X / KP2)  [edge-triggered]  (also Y)
  Btn  7 (RB)      → Fire photon torpedo    (keyboard: E / KP9)  [held]  (also X)
  Btn 10 (Select)  → Attract / exit         (keyboard: F1)       [edge-triggered]
  Btn 11 (Start)   → Start game (attract) / Pause (game)         [edge-triggered]
  Btn 14 (RS click)→ Toggle own robot AI   (keyboard: F3/F4)    [edge-triggered]
  Left  Trigger    → Impulse engines        (keyboard: S / KP5)  [held]
  Right Trigger    → Fire phasers           (keyboard: Q / KP7)  [edge-triggered]  (also A)
  Left  stick X    → Rotate CCW / CW       (keyboard: A,D / KP4,6)
  Right stick left → Shields→Energy        (keyboard: Z / KP1)  [held]
  Right stick right→ Energy→Shields        (keyboard: C / KP3)  [held]
  D-Pad Up         → Toggle planet          (keyboard: F5)       [edge-triggered]
  D-Pad Down       → Toggle sound           (keyboard: F8)       [edge-triggered]

Axis layout (verified via controller_test.py):
  Axis 0 = Left  stick X      (left = -1, right = +1)
  Axis 5 = Left  trigger      (rest ≈ 0, pressed → +1)
  Axis 2 = Right stick X      (left = -1, right = +1)
  Axis 4 = Right trigger      (rest ≈ 0, pressed → -1  ← inverted!)

Buttons verified: 0=A, 1=B, 3=X, 4=Y, 6=LB, 7=RB, 10=Select, 11=Start, 14=RS click.
"""

from __future__ import annotations

import pygame

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

TRIGGER_THRESHOLD = 0.5   # trigger axis value counted as "pressed"
STICK_THRESHOLD   = 0.5   # analog stick dead zone

# ---------------------------------------------------------------------------
# Button indices
# ---------------------------------------------------------------------------

BTN_PHASER        = 0    # A button → fire phasers (Q)        [verified]  [edge]
BTN_CLOAK         = 1    # B button → cloak (W)               [verified]  [held]
BTN_PHOTON_X      = 3    # X button → fire photon torpedo (E) [verified]  [held]
BTN_HYPERSPACE_Y  = 4    # Y button → hyperspace (X)          [verified]  [edge]
# BTN 5 (?) — unassigned
BTN_HYPERSPACE    = 6    # LB       → hyperspace (X)          [verified]  [edge]
BTN_PHOTON        = 7    # RB       → fire photon torpedo (E) [verified]  [held]
BTN_SELECT        = 10   # Select   → attract/exit (F1)       [verified]
BTN_START         = 11   # Start    → start game / pause      [verified]
BTN_RS_CLICK      = 14   # RS click → toggle own robot AI     [verified]
# Energy transfer uses right stick X axis only — no button

# ---------------------------------------------------------------------------
# Axis indices (standard SDL2 Xbox mapping)
# ---------------------------------------------------------------------------

AXIS_LX = 0    # Left  stick horizontal  (left = -1, right = +1)   [verified]
AXIS_LT = 5    # Left  trigger           (rest ≈ 0,  pressed → +1) [verified]
AXIS_RX = 2    # Right stick horizontal  (left = -1, right = +1)   [verified]
AXIS_RT = 4    # Right trigger           (rest ≈ 0,  pressed → -1) [verified, INVERTED]


# ---------------------------------------------------------------------------
# JoystickState
# ---------------------------------------------------------------------------

class JoystickState:
    """Per-joystick state tracker with just-pressed edge detection.

    Call update() once per frame (after pygame.event.get()) before reading
    any state properties.
    """

    def __init__(self, joystick: pygame.joystick.Joystick) -> None:
        self._joy = joystick
        try:
            self._joy.init()          # no-op on pygame 2.x, needed for 1.x
        except Exception:
            pass
        n = self._joy.get_numbuttons()
        self._prev_buttons: list[bool] = [False] * max(n, 16)
        self._prev_lt: bool = False
        self._prev_rt: bool = False
        self._prev_hat_up: bool = False
        self._prev_hat_dn: bool = False
        self.just_pressed_buttons: dict[int, bool] = {}
        self.just_pressed_lt: bool = False
        self.just_pressed_rt: bool = False
        self.just_pressed_hat_up: bool = False
        self.just_pressed_hat_dn: bool = False

    def update(self) -> None:
        """Poll current state and compute just-pressed edges for this frame."""
        try:
            n = self._joy.get_numbuttons()
            curr = [bool(self._joy.get_button(i)) for i in range(n)]
        except Exception:
            curr = []

        prev = self._prev_buttons
        self.just_pressed_buttons = {
            i: True
            for i, c in enumerate(curr)
            if c and not (prev[i] if i < len(prev) else False)
        }
        self._prev_buttons = curr + [False] * max(0, len(prev) - len(curr))

        lt_now = self.trigger_lt()
        rt_now = self.trigger_rt()
        self.just_pressed_lt = lt_now and not self._prev_lt
        self.just_pressed_rt = rt_now and not self._prev_rt
        self._prev_lt = lt_now
        self._prev_rt = rt_now

        hat_up_now = self.hat_y() == 1
        hat_dn_now = self.hat_y() == -1
        self.just_pressed_hat_up = hat_up_now and not self._prev_hat_up
        self.just_pressed_hat_dn = hat_dn_now and not self._prev_hat_dn
        self._prev_hat_up = hat_up_now
        self._prev_hat_dn = hat_dn_now

    # ------------------------------------------------------------------
    # Raw state readers
    # ------------------------------------------------------------------

    def button(self, idx: int) -> bool:
        """Return True if button *idx* is held this frame."""
        try:
            return bool(self._joy.get_button(idx))
        except Exception:
            return False

    def _axis(self, idx: int) -> float:
        """Raw axis value, or 0.0 on error."""
        try:
            return float(self._joy.get_axis(idx))
        except Exception:
            return 0.0

    def trigger_lt(self) -> bool:
        """Left trigger — True when pressed past TRIGGER_THRESHOLD (thrust)."""
        return self._axis(AXIS_LT) > TRIGGER_THRESHOLD

    def trigger_rt(self) -> bool:
        """Right trigger — True when pressed past TRIGGER_THRESHOLD (phasers).

        This controller's right trigger (axis 4) goes NEGATIVE when pressed,
        so we check axis < -TRIGGER_THRESHOLD.
        """
        return self._axis(AXIS_RT) < -TRIGGER_THRESHOLD

    def thrust(self) -> bool:
        """Left trigger held — impulse engines."""
        return self.trigger_lt()

    def hat_x(self) -> int:
        """D-Pad horizontal value: -1 (left), 0 (centre), 1 (right)."""
        try:
            if self._joy.get_numhats() > 0:
                return self._joy.get_hat(0)[0]
        except Exception:
            pass
        return 0

    def hat_y(self) -> int:
        """D-Pad vertical value: 1 (up), 0 (centre), -1 (down)."""
        try:
            if self._joy.get_numhats() > 0:
                return self._joy.get_hat(0)[1]
        except Exception:
            pass
        return 0

    def rotate_left(self) -> bool:
        """True when left stick points left."""
        return self._axis(AXIS_LX) < -STICK_THRESHOLD

    def rotate_right(self) -> bool:
        """True when left stick points right."""
        return self._axis(AXIS_LX) > STICK_THRESHOLD

    def right_stick_left(self) -> bool:
        """Right stick left — shields→energy transfer."""
        return self._axis(AXIS_RX) < -STICK_THRESHOLD

    def right_stick_right(self) -> bool:
        """Right stick right — energy→shields transfer."""
        return self._axis(AXIS_RX) > STICK_THRESHOLD


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

def init_joysticks() -> list[JoystickState]:
    """Initialise the pygame joystick subsystem; return up to 2 JoystickState objects.

    Player 1 gets index 0, player 2 gets index 1.
    Returns an empty list if no controllers are connected.
    Must be called after pygame.init().
    """
    try:
        pygame.joystick.init()
    except Exception:
        return []
    states: list[JoystickState] = []
    for i in range(min(2, pygame.joystick.get_count())):
        try:
            states.append(JoystickState(pygame.joystick.Joystick(i)))
        except Exception:
            pass
    return states
