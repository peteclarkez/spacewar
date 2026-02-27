"""
Robot AI — two distinct personalities matching the 1985 original.

Left Robot  (F3) — Enterprise / "Defensive":
  Fires phasers only, random thrust, very rarely uses hyperspace.

Right Robot (F4) — Klingon / "Offensive":
  Always faces opponent, fires phasers OR torpedoes by range, random thrust.

Both robots continuously balance S and E bars toward equality.
"""

from __future__ import annotations
import random

from spacewar.constants import (
    PHASER_RANGE, PROB_IMPULSE, PROB_PHOTON, PROB_HYPER,
    PLAYER_ENT, PLAYER_KLN,
    VIRTUAL_W, VIRTUAL_H,
)
from spacewar import trig as T


def _balance_energy(ship) -> None:
    """Continuously equalise shields and energy (1 unit per swap period)."""
    if ship.shields < ship.energy:
        ship.energy_to_shields()
    elif ship.energy < ship.shields:
        ship.shields_to_energy()


def _in_phaser_range(ax: float, ay: float, bx: float, by: float) -> bool:
    """Return True if target is within PHASER_RANGE on both axes."""
    return abs(ax - bx) <= PHASER_RANGE and abs(ay - by) <= PHASER_RANGE


def left_robot_tick(ship, opponent, torp_pool, gravity_on: bool, tick: int) -> None:
    """
    Enterprise left robot — defensive.
    Controls: rotate-to-face, fire phasers when in range, random thrust,
    energy balance.  Does NOT fire torpedoes.
    """
    _balance_energy(ship)

    if ship.energy <= 0:
        return

    # Aim toward opponent
    dx = opponent.x - ship.x
    dy = opponent.y - ship.y
    bearing = T.angle_between(dx, dy)
    ship.angle = bearing

    # Fire phasers when opponent in range
    if _in_phaser_range(ship.x, ship.y, opponent.x, opponent.y):
        if ship.can_fire_phaser():
            ship.fire_phaser()
            # Caller (game loop) handles actual ray cast

    # Random thrust
    if random.randint(0, PROB_IMPULSE - 1) == 0:
        ship.apply_thrust()

    # Rare hyperspace
    if random.randint(0, PROB_HYPER - 1) == 0:
        if ship.can_hyperspace(True) and not ship.hyper_debounce:
            ship.consume_hyperspace_energy()
            dest_x = random.uniform(20, VIRTUAL_W - 20)
            dest_y = random.uniform(20, VIRTUAL_H - 20)
            ship.particles.start_hyperspace(ship.x, ship.y, dest_x, dest_y)


def right_robot_tick(ship, opponent, torp_pool, gravity_on: bool, tick: int) -> None:
    """
    Klingon right robot — offensive.
    Controls: always faces opponent, fires phasers or torpedoes by range,
    random thrust, energy balance.
    """
    _balance_energy(ship)

    # Always rotate to face opponent
    dx = opponent.x - ship.x
    dy = opponent.y - ship.y
    bearing = T.angle_between(dx, dy)
    ship.angle = bearing

    in_range = _in_phaser_range(ship.x, ship.y, opponent.x, opponent.y)

    # Random fire decision (1/PROB_PHOTON chance per tick)
    if random.randint(0, PROB_PHOTON - 1) == 0:
        if ship.energy > 0:
            if in_range and ship.can_fire_phaser():
                ship.fire_phaser()
            elif not in_range:
                # Fire torpedo
                if not ship.torp_debounce and ship.energy >= 1:
                    ship.consume_torpedo_energy()
                    torp_pool.fire(ship.x, ship.y, ship.vx, ship.vy, ship.angle)

    # Ensure torpedo debounce resets if not firing
    ship.torp_debounce = False   # robots always re-enable each tick after deciding

    # Random thrust
    if random.randint(0, PROB_IMPULSE - 1) == 0 and ship.energy > 0:
        ship.apply_thrust()

    # Rare hyperspace
    if random.randint(0, PROB_HYPER - 1) == 0:
        if ship.energy >= 8 and not ship.particles.active:
            ship.consume_hyperspace_energy()
            dest_x = random.uniform(20, VIRTUAL_W - 20)
            dest_y = random.uniform(20, VIRTUAL_H - 20)
            ship.particles.start_hyperspace(ship.x, ship.y, dest_x, dest_y)
