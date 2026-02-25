"""phaser.py — phaser beam firing, hit detection, and erase.

Mirrors PHASER.ASM.

The phaser beam is a ray cast in the ship's current facing direction.
Key parameters (from PHASER.EQU):
  PHASER_RANGE   = 96  px  — maximum ray length
  Dead zone      = first 9 pixels — no hit-check
  Hit interval   = every 8 pixels (PHASER_TO_OBJ_RANGE)
  Damage to ships: PHASER_DAMAGE = 2 shields
  Effect on torps: set EFLG_EXPLODING
  Planet:          stop ray if encountered

State machine (PHST field on ship object):
  255 (PHASER_IDLE) — not firing
  24  (PHASER_DELAY) — just fired; count down each tick
  20  (PHASER_ERASE) — main.py triggers erase pass this tick
  19..1              — cooldown
  0                  — reset to PHASER_IDLE

Public API
----------
fire_phaser_enterprise(state, surface)
fire_phaser_klingon(state, surface)
erase_phaser_enterprise(state, surface)
erase_phaser_klingon(state, surface)
"""

from __future__ import annotations

import pygame

from .constants import (
    ENT_OBJ, KLN_OBJ,
    EFLG_ACTIVE, EFLG_EXPLODING,
    PHASER_IDLE, PHASER_DELAY, PHASER_ERASE, PHASER_RANGE,
    PHASER_TO_OBJ_RANGE, PHASER_DAMAGE, PHASER_FIRE_ENERGY,
    PHASER_SOUND, PLANET_BIT,
    PLANET_X, PLANET_Y, PLANET_RANGE,
    Y_SCALE,
)
from .trig import cos_lookup, sin_lookup
from .init import GameState

# Colour used for the phaser beam (white monochrome)
PHASER_COLOR = (255, 255, 255)

# Pixels at the muzzle that are skipped before hit checks begin
_DEAD_ZONE: int = 9


# ---------------------------------------------------------------------------
# Internal ray walker
# ---------------------------------------------------------------------------

def _draw_phaser_ray(
    state: GameState,
    surface: pygame.Surface,
    ship_idx: int,
    compare: bool,
    color: tuple | None = None,
) -> int:
    """Step along the phaser ray, drawing pixels and optionally checking hits.

    Args:
        state:    game state
        surface:  pygame surface to draw on (screen coordinates)
        ship_idx: ENT_OBJ or KLN_OBJ
        compare:  True → draw beam + check hits; False → erase (draw black)

    Returns:
        Number of pixels stepped (used to save phaser_count for erase pass).

    Mirrors the Phaser_Ray inner loop in PHASER.ASM:
    - Uses CMPS_FLAG for hit-detect vs erase mode
    - Steps in cos/sin direction
    - Skip dead zone (first 9 pixels)
    - Every 8 pixels: Manhattan-distance hit check against all active objects
    """
    ship = state.objects[ship_idx]

    if compare:
        ox = ship.x
        oy = ship.y
        oa = ship.angle
    else:
        # Erase pass uses saved origin/angle, not current ship position
        ox = ship.phaser_x
        oy = ship.phaser_y
        oa = ship.phaser_angle

    # Direction unit vector from sin/cos table, scaled to sub-pixel steps
    # We use floating-point for the ray accumulator (integer would drift)
    dx = cos_lookup(oa) / 32767.0   # normalised to ±1.0
    dy = sin_lookup(oa) / 32767.0

    if color is None:
        color = PHASER_COLOR if compare else (0, 0, 0)

    rx = float(ox)
    ry = float(oy)
    count = 0
    hit_interval_counter = 0

    max_range = ship.phaser_count if not compare else PHASER_RANGE

    for step in range(max_range):
        rx += dx
        ry += dy
        count += 1

        # Draw pixel (Y doubled for screen coords)
        sx = int(rx)
        sy = int(ry)
        if 0 <= sx < surface.get_width() and 0 <= sy * Y_SCALE < surface.get_height():
            surface.set_at((sx, sy * Y_SCALE), color)
            if Y_SCALE > 1:
                surface.set_at((sx, sy * Y_SCALE + 1), color)

        # Skip dead zone — no hit checks for the first _DEAD_ZONE pixels
        if step < _DEAD_ZONE:
            continue

        # Hit-check every PHASER_TO_OBJ_RANGE pixels
        hit_interval_counter += 1
        if hit_interval_counter < PHASER_TO_OBJ_RANGE:
            continue
        hit_interval_counter = 0

        if not compare:
            continue   # erase pass — no hits

        # Check planet collision
        if state.planet_enable & PLANET_BIT:
            if abs(sx - PLANET_X) < PLANET_RANGE and abs(sy - PLANET_Y) < PLANET_RANGE:
                break   # ray stops at planet

        # Check all active objects for Manhattan-distance hit
        for i, obj in enumerate(state.objects):
            if obj.eflg == EFLG_ACTIVE:
                if abs(obj.x - sx) < PHASER_TO_OBJ_RANGE and abs(obj.y - sy) < PHASER_TO_OBJ_RANGE:
                    # Determine if hit target is a ship or torpedo
                    if i == ENT_OBJ or i == KLN_OBJ:
                        obj.shields -= PHASER_DAMAGE
                    else:
                        # Torpedo hit
                        obj.eflg = EFLG_EXPLODING
                        obj.exps = 8

    return count


# ---------------------------------------------------------------------------
# Fire and erase — Enterprise
# ---------------------------------------------------------------------------

def fire_phaser_enterprise(state: GameState, surface: pygame.Surface) -> None:
    """Fire Enterprise phaser beam.  Mirrors Phaser_Ent in PHASER.ASM."""
    ship = state.objects[ENT_OBJ]
    if ship.phaser_state != PHASER_IDLE:
        return
    if ship.energy <= 0:
        return

    ship.energy -= PHASER_FIRE_ENERGY
    ship.phaser_state = PHASER_DELAY

    # Save origin + angle for the erase pass
    ship.phaser_x = ship.x
    ship.phaser_y = ship.y
    ship.phaser_angle = ship.angle

    count = _draw_phaser_ray(state, surface, ENT_OBJ, compare=True)
    ship.phaser_count = count

    state.sound_flag |= PHASER_SOUND


def erase_phaser_enterprise(state: GameState, surface: pygame.Surface) -> None:
    """Erase Enterprise phaser beam (replay ray in black).  Mirrors Erase_Phaser."""
    _draw_phaser_ray(state, surface, ENT_OBJ, compare=False)


# ---------------------------------------------------------------------------
# Fire and erase — Klingon
# ---------------------------------------------------------------------------

def fire_phaser_klingon(state: GameState, surface: pygame.Surface) -> None:
    """Fire Klingon phaser beam.  Mirrors Phaser_Kln in PHASER.ASM."""
    ship = state.objects[KLN_OBJ]
    if ship.phaser_state != PHASER_IDLE:
        return
    if ship.energy <= 0:
        return

    ship.energy -= PHASER_FIRE_ENERGY
    ship.phaser_state = PHASER_DELAY

    ship.phaser_x = ship.x
    ship.phaser_y = ship.y
    ship.phaser_angle = ship.angle

    count = _draw_phaser_ray(state, surface, KLN_OBJ, compare=True)
    ship.phaser_count = count

    state.sound_flag |= PHASER_SOUND


def erase_phaser_klingon(state: GameState, surface: pygame.Surface) -> None:
    """Erase Klingon phaser beam (replay ray in black).  Mirrors Erase_Phaser."""
    _draw_phaser_ray(state, surface, KLN_OBJ, compare=False)


# ---------------------------------------------------------------------------
# Redraw helpers — called each frame after background blit to restore beam
# ---------------------------------------------------------------------------

def redraw_phaser_enterprise(state: GameState, surface: pygame.Surface) -> None:
    """Redraw the Enterprise phaser beam in white (after the background blit erased it).

    Only draws when phaser_state is in the visible window (PHASER_ERASE < state < PHASER_IDLE).
    Uses the saved origin/angle/count so the ray is pixel-identical to the original.
    No hit detection is performed.
    """
    ship = state.objects[ENT_OBJ]
    ps = ship.phaser_state
    if ps == PHASER_IDLE or ps <= PHASER_ERASE:
        return
    _draw_phaser_ray(state, surface, ENT_OBJ, compare=False, color=PHASER_COLOR)


def redraw_phaser_klingon(state: GameState, surface: pygame.Surface) -> None:
    """Redraw the Klingon phaser beam in white (after the background blit erased it)."""
    ship = state.objects[KLN_OBJ]
    ps = ship.phaser_state
    if ps == PHASER_IDLE or ps <= PHASER_ERASE:
        return
    _draw_phaser_ray(state, surface, KLN_OBJ, compare=False, color=PHASER_COLOR)
