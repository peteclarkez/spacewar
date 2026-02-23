"""torpedo.py — photon torpedo firing logic.

Mirrors TORP.ASM.

Each ship has 7 torpedo slots.  A torpedo is launched by finding the first
inactive slot, initialising it with the ship's position + facing offset and
velocity + facing impulse, and marking it active.

Torpedoes drain 1 energy unit every PHOTON_TIME ticks (managed in physics.py).
Death when ENRGY (energy) reaches 0 → eflg set to EFLG_EXPLODING.

Public API
----------
fire_enterprise_torpedo(state)   — fire one Enterprise torpedo (if possible)
fire_klingon_torpedo(state)      — fire one Klingon torpedo (if possible)
find_free_torpedo(state, start, end) -> int | None
"""

from .constants import (
    ENT_OBJ, KLN_OBJ,
    ENT_TORP_START, ENT_TORP_END,
    KLN_TORP_START, KLN_TORP_END,
    EFLG_ACTIVE, EFLG_INACTIVE,
    TORP_FIRE_BIT, PHOTON_LAUNCH_ENERGY, PHOTON_ENERGY,
    PHOTON_SOUND, FIRE_SCALE,
    VIRTUAL_W, VIRTUAL_H, WRAP_FACTOR,
)
from .trig import cos_lookup, sin_lookup
from .init import GameObject, GameState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def find_free_torpedo(state: GameState, start: int, end: int) -> int | None:
    """Return the index of the first inactive torpedo slot, or None.

    Mirrors the 'find free slot' loop in TORP.ASM.
    start, end — half-open range of torpedo indices to search.
    """
    for i in range(start, end):
        if state.objects[i].eflg == EFLG_INACTIVE:
            return i
    return None


def _launch_torpedo(ship: GameObject, torp: GameObject) -> None:
    """Copy ship state into torpedo slot and apply launch impulse.

    Mirrors the torpedo initialisation in TORP.ASM:
    - Position = ship position + 8 × facing direction (3 left-shifts of cos/sin)
    - Velocity  = ship velocity + cos/sin(angle) >> FIRE_SCALE
    """
    angle = ship.angle

    # Torpedo spawns at ship position with a tiny sub-pixel fractional nudge
    # in the facing direction (cos/sin >> 3 = max ~4096 out of 65536 ≈ 0.06px).
    # The nudge stays in the fractional word; integer carry is 0 almost always.
    # This mirrors the TORP.ASM SAR-then-ADD-to-XDISL pattern.
    cos_val = cos_lookup(angle)
    sin_val = sin_lookup(angle)

    new_x_frac = ship.x_frac + (cos_val >> 3)
    carry_x = new_x_frac >> 16
    torp.x_frac = new_x_frac & 0xFFFF
    torp.x = ship.x + carry_x

    new_y_frac = ship.y_frac + (sin_val >> 3)
    carry_y = new_y_frac >> 16
    torp.y_frac = new_y_frac & 0xFFFF
    torp.y = ship.y + carry_y

    # Torpedo velocity = ship velocity + fire impulse
    # FIRE_SCALE=2 → divide cos/sin by 4 for launch speed
    fire_vx = cos_val >> FIRE_SCALE
    fire_vy = sin_val >> FIRE_SCALE

    # Add fire impulse to ship velocity (fractional carry)
    new_vx_frac = ship.vx_frac + (fire_vx & 0xFFFF)
    carry_x = new_vx_frac >> 16
    torp.vx_frac = new_vx_frac & 0xFFFF
    torp.vx = ship.vx + (fire_vx >> 16) + carry_x

    new_vy_frac = ship.vy_frac + (fire_vy & 0xFFFF)
    carry_y = new_vy_frac >> 16
    torp.vy_frac = new_vy_frac & 0xFFFF
    torp.vy = ship.vy + (fire_vy >> 16) + carry_y

    torp.angle = angle
    torp.rotate = 0
    torp.flags = 0
    torp.fire = 0
    torp.energy = PHOTON_ENERGY   # ENRGY = 40; lifetime fuel
    torp.eflg = EFLG_ACTIVE
    torp.uflg = 0
    torp.exps = 0

    # Wrap torpedo starting position onto the virtual screen
    torp.x = torp.x % VIRTUAL_W
    torp.y = torp.y % VIRTUAL_H


def _fire(state: GameState, ship_idx: int, torp_start: int, torp_end: int) -> None:
    """Common fire routine for both ships.

    Guards: ship must be active, have energy, and the torp debounce must be clear.
    """
    ship = state.objects[ship_idx]

    # Must have dilithium energy to fire
    if ship.energy <= 0:
        return

    # Torp debounce — prevent double-firing on a held key
    if ship.fire & TORP_FIRE_BIT:
        return

    slot = find_free_torpedo(state, torp_start, torp_end)
    if slot is None:
        return

    # Cost to launch
    ship.energy -= PHOTON_LAUNCH_ENERGY
    ship.fire |= TORP_FIRE_BIT    # set debounce

    _launch_torpedo(ship, state.objects[slot])

    # Signal sound system
    state.sound_flag |= PHOTON_SOUND


# ---------------------------------------------------------------------------
# Public fire functions
# ---------------------------------------------------------------------------

def fire_enterprise_torpedo(state: GameState) -> None:
    """Fire one Enterprise photon torpedo.  Mirrors TORP.ASM fire_ent."""
    _fire(state, ENT_OBJ, ENT_TORP_START, ENT_TORP_END)


def fire_klingon_torpedo(state: GameState) -> None:
    """Fire one Klingon photon torpedo.  Mirrors TORP.ASM fire_kln."""
    _fire(state, KLN_OBJ, KLN_TORP_START, KLN_TORP_END)
