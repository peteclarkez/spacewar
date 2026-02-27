"""gravity.py — bowl (linear) gravity toward the planet centre.

Public API
----------
apply_gravity(obj)          — one object, one tick
update_gravity_all(state)   — all 16 active objects (if gravity flag set)
"""

from .constants import (
    PLANET_X, PLANET_Y, GRAVITY_BIT, EFLG_ACTIVE,
    NUM_OBJECTS,
)
from .init import GameObject, GameState


# ---------------------------------------------------------------------------
# Single-object gravity step
# ---------------------------------------------------------------------------

def apply_gravity(obj: GameObject) -> None:
    """Add one tick of bowl gravity to obj's fractional velocity.

    Formula:
        dx = obj.x - PLANET_X
        dy = obj.y - PLANET_Y
        accel_x = -dx * 8    (SAL bx,3 then NEG if positive delta)
        accel_y = -dy * 8

    The acceleration is added to the fractional velocity word.  Carry
    propagates to the integer velocity word on the next position update.
    """
    dx = obj.x - PLANET_X
    dy = obj.y - PLANET_Y

    # Acceleration = negative of delta, scaled by 8
    accel_x = -(dx << 3)
    accel_y = -(dy << 3)

    # Add to fractional velocity with carry propagation
    _add_accel(obj, accel_x, accel_y)


def _add_accel(obj: GameObject, accel_x: int, accel_y: int) -> None:
    """Adds signed acceleration to fractional velocity with carry propagation."""
    new_vx_frac = obj.vx_frac + accel_x
    carry_x = new_vx_frac >> 16          # −1, 0, or +1
    obj.vx_frac = new_vx_frac & 0xFFFF
    obj.vx += carry_x

    new_vy_frac = obj.vy_frac + accel_y
    carry_y = new_vy_frac >> 16
    obj.vy_frac = new_vy_frac & 0xFFFF
    obj.vy += carry_y


# ---------------------------------------------------------------------------
# Apply gravity to all active objects
# ---------------------------------------------------------------------------

def update_gravity_all(state: GameState) -> None:
    """Apply bowl gravity to every active object.

    Called each tick when planet_enable & GRAVITY_BIT is set.
    """
    if not (state.planet_enable & GRAVITY_BIT):
        return
    for obj in state.objects:
        if obj.eflg == EFLG_ACTIVE:
            apply_gravity(obj)
