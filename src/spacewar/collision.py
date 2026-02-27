"""collision.py — collision detection and response.

All collision detection uses Manhattan distance (NOT Euclidean):
    abs(dx) < range  AND  abs(dy) < range

Collision order:
  1. Ship-ship:        Enterprise vs Klingon (range 16)
  2. Ent ship vs KLN torps  (range 8, PHOTON_DAMAGE=4)
  3. Ent ship vs ENT torps  (range 8, PHOTON_DAMAGE=4) — self-hit possible!
  4. Kln ship vs ENT torps  (range 8, PHOTON_DAMAGE=4)
  5. Kln ship vs KLN torps  (range 8, PHOTON_DAMAGE=4) — self-hit possible!
  6. ENT torps vs KLN torps (range 6, both explode)
  7. Planet vs all active objects (if PLANET_BIT set)

Ship-ship collision is inelastic (velocities halved and swapped), NO shield damage.
Death: shields < 0  (signed-byte underflow).

Public API
----------
check_all_collisions(state)         — run all collision checks for one tick
check_death(state) -> int           — returns dead ship idx or -1
"""

from .constants import (
    ENT_OBJ, KLN_OBJ,
    ENT_TORP_START, ENT_TORP_END,
    KLN_TORP_START, KLN_TORP_END,
    EFLG_ACTIVE, EFLG_EXPLODING,
    SHIP_TO_SHIP_RANGE, SHIP_TO_TORP_RANGE, TORP_TO_TORP_RANGE,
    BOUNCE_FACTOR, PHOTON_DAMAGE, PLANET_DAMAGE,
    PLANET_X, PLANET_Y, PLANET_RANGE, PLANET_BIT,
    TORP_HIT_SOUND,
)
from .init import GameObject, GameState


# ---------------------------------------------------------------------------
# Helper: Manhattan distance test
# ---------------------------------------------------------------------------

def _in_range(a: GameObject, b: GameObject, r: int) -> bool:
    """Return True if a and b are within Manhattan distance r.

    abs(dx) < r  AND  abs(dy) < r
    """
    return abs(a.x - b.x) < r and abs(a.y - b.y) < r


def _in_range_xy(x1: int, y1: int, x2: int, y2: int, r: int) -> bool:
    """Range check against explicit coordinates."""
    return abs(x1 - x2) < r and abs(y1 - y2) < r


# ---------------------------------------------------------------------------
# Ship-ship collision (inelastic velocity swap, no shield damage)
# ---------------------------------------------------------------------------

def _ship_ship_collision(state: GameState) -> None:
    """Handle Enterprise/Klingon ship-ship collision.

    - Velocities halved and swapped (SAR = signed arithmetic right-shift)
    - Ships bounced apart by BOUNCE_FACTOR pixels
    - NO shield damage
    """
    ent = state.objects[ENT_OBJ]
    kln = state.objects[KLN_OBJ]

    if ent.eflg != EFLG_ACTIVE or kln.eflg != EFLG_ACTIVE:
        return

    if not _in_range(ent, kln, SHIP_TO_SHIP_RANGE):
        return

    # Inelastic swap — each ship gets ½ the other's velocity (SAR = ÷2, signed)
    # Integer parts
    ent_vx, ent_vy = ent.vx, ent.vy
    kln_vx, kln_vy = kln.vx, kln.vy

    ent.vx = kln_vx >> 1   # signed right-shift (Python >> on negative int = floor div)
    ent.vy = kln_vy >> 1
    kln.vx = ent_vx >> 1
    kln.vy = ent_vy >> 1
    # Clear fractional velocity on collision
    ent.vx_frac = 0
    ent.vy_frac = 0
    kln.vx_frac = 0
    kln.vy_frac = 0

    # Bounce apart — push each ship away from the other by BOUNCE_FACTOR pixels
    dx = ent.x - kln.x
    dy = ent.y - kln.y
    if dx >= 0:
        ent.x += BOUNCE_FACTOR
        kln.x -= BOUNCE_FACTOR
    else:
        ent.x -= BOUNCE_FACTOR
        kln.x += BOUNCE_FACTOR
    if dy >= 0:
        ent.y += BOUNCE_FACTOR
        kln.y -= BOUNCE_FACTOR
    else:
        ent.y -= BOUNCE_FACTOR
        kln.y += BOUNCE_FACTOR


# ---------------------------------------------------------------------------
# Ship-torpedo collision
# ---------------------------------------------------------------------------

def _ship_torp_collision(ship: GameObject, torps: list[tuple[int, GameObject]]) -> bool:
    """Check one ship against a list of (index, torpedo) pairs.

    Ship loses PHOTON_DAMAGE shields per hit; torpedo set to EFLG_EXPLODING.
    Returns True if any hit occurred.
    """
    if ship.eflg != EFLG_ACTIVE:
        return False

    hit = False
    for _, torp in torps:
        if torp.eflg != EFLG_ACTIVE:
            continue
        if _in_range(ship, torp, SHIP_TO_TORP_RANGE):
            ship.shields -= PHOTON_DAMAGE
            torp.eflg = EFLG_EXPLODING
            torp.exps = 8
            hit = True
    return hit


# ---------------------------------------------------------------------------
# Torpedo-torpedo collision
# ---------------------------------------------------------------------------

def _torp_torp_collision(
    ent_torps: list[tuple[int, GameObject]],
    kln_torps: list[tuple[int, GameObject]],
) -> bool:
    """Check all Enterprise torps against all Klingon torps.

    Both torpedoes set to EFLG_EXPLODING.
    Returns True if any collision occurred.
    """
    hit = False
    for _, et in ent_torps:
        if et.eflg != EFLG_ACTIVE:
            continue
        for _, kt in kln_torps:
            if kt.eflg != EFLG_ACTIVE:
                continue
            if _in_range(et, kt, TORP_TO_TORP_RANGE):
                et.eflg = EFLG_EXPLODING
                et.exps = 8
                kt.eflg = EFLG_EXPLODING
                kt.exps = 8
                hit = True
    return hit


# ---------------------------------------------------------------------------
# Planet collision
# ---------------------------------------------------------------------------

def _planet_collision(state: GameState) -> bool:
    """Check all active objects against the planet (if PLANET_BIT set).

    Ships: lose PLANET_DAMAGE shields.
    Torpedoes: explode immediately.
    Returns True if any torpedo hit the planet.
    """
    if not (state.planet_enable & PLANET_BIT):
        return False

    torp_hit = False
    for i, obj in enumerate(state.objects):
        if obj.eflg != EFLG_ACTIVE:
            continue
        if _in_range_xy(obj.x, obj.y, PLANET_X, PLANET_Y, PLANET_RANGE):
            if i == ENT_OBJ or i == KLN_OBJ:
                obj.shields -= PLANET_DAMAGE
            else:
                obj.eflg = EFLG_EXPLODING
                obj.exps = 8
                torp_hit = True
    return torp_hit


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def check_all_collisions(state: GameState) -> None:
    """Run all collision checks."""
    objs = state.objects

    # Build torpedo lists for convenience
    ent_torps = [(i, objs[i]) for i in range(ENT_TORP_START, ENT_TORP_END)]
    kln_torps = [(i, objs[i]) for i in range(KLN_TORP_START, KLN_TORP_END)]

    # 1. Ship vs ship
    _ship_ship_collision(state)

    # 2-6. Torpedo collisions — accumulate any hit for the hit sound
    torp_hit = False
    torp_hit |= _ship_torp_collision(objs[ENT_OBJ], kln_torps)   # 2. ENT vs KLN torps
    torp_hit |= _ship_torp_collision(objs[ENT_OBJ], ent_torps)   # 3. ENT vs own torps
    torp_hit |= _ship_torp_collision(objs[KLN_OBJ], ent_torps)   # 4. KLN vs ENT torps
    torp_hit |= _ship_torp_collision(objs[KLN_OBJ], kln_torps)   # 5. KLN vs own torps
    torp_hit |= _torp_torp_collision(ent_torps, kln_torps)        # 6. torp vs torp
    torp_hit |= _planet_collision(state)                          # 7. planet vs torps

    if torp_hit:
        state.sound_flag |= TORP_HIT_SOUND


def check_death(state: GameState) -> int:
    """Check whether either ship has died (shields < 0).

    Returns ENT_OBJ, KLN_OBJ, or -1 (no death this tick).
    """
    ent = state.objects[ENT_OBJ]
    kln = state.objects[KLN_OBJ]

    if ent.eflg == EFLG_ACTIVE and ent.shields < 0:
        return ENT_OBJ
    if kln.eflg == EFLG_ACTIVE and kln.shields < 0:
        return KLN_OBJ
    return -1
