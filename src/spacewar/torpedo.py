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
    PHOTON_SOUND,
    VIRTUAL_W, VIRTUAL_H,
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
    - Position = ship position + ~7px in the facing direction
    - Velocity  = ship velocity + ~3 px/tick in the facing direction
    """
    angle = ship.angle
    cos_val = cos_lookup(angle)   # ±32767 signed 16-bit
    sin_val = sin_lookup(angle)

    # Position: spawn ~15 virtual pixels ahead of the ship centre.
    # 32767 >> 11 = 15, which is safely beyond SHIP_TO_TORP_RANGE=8 so the
    # torpedo does not immediately collide with the firing ship.
    torp.x = (ship.x + (cos_val >> 11)) % VIRTUAL_W
    torp.y = (ship.y + (sin_val >> 11)) % VIRTUAL_H
    torp.x_frac = ship.x_frac
    torp.y_frac = ship.y_frac

    # Velocity: ship velocity plus ~3 px/tick launch impulse.
    # 32767 >> 13 = 3; preserves sign for all quadrants.
    torp.vx = ship.vx + (cos_val >> 13)
    torp.vy = ship.vy + (sin_val >> 13)
    torp.vx_frac = ship.vx_frac
    torp.vy_frac = ship.vy_frac

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
