"""
Phaser weapon — ray casting, hit detection, and rendering.

A phaser ray is cast from the ship outward in the ship's facing direction.
The first PHASER_SKIP pixels are a dead zone (prevents self-hit).
Hit detection is checked every PHASER_TO_OBJ_RANGE pixels along the ray.
The ray terminates on hitting a torpedo, ship, or planet.
"""

from __future__ import annotations
import math
from dataclasses import dataclass

from spacewar.constants import (
    PHASER_RANGE, PHASER_ERASE, PHASER_DELAY,
    PHASER_TO_OBJ_RANGE, PHASER_DAMAGE, PHASER_SKIP,
    PLANET_X, PLANET_Y, PLANET_RANGE,
    PLAYER_ENT, PLAYER_KLN,
    WHITE, Y_SCALE,
)
from spacewar import trig as T


@dataclass
class Phaser:
    """State for one ship's phaser."""
    active:    bool  = False   # ray is visible / in flight
    timer:     int   = 0       # counts up; erased at PHASER_ERASE, reset at PHASER_DELAY
    owner:     int   = PLAYER_ENT
    start_x:   float = 0.0    # origin (ship position at fire)
    start_y:   float = 0.0
    end_x:     float = 0.0    # where the ray terminated
    end_y:     float = 0.0
    hit:       bool  = False

    def reset(self) -> None:
        self.active = self.hit = False
        self.timer  = 0

    def tick(self) -> None:
        """Advance the phaser timer each game tick."""
        if self.timer > 0:
            self.timer -= 1
            if self.timer == 0:
                self.active = False


def cast_phaser(
    phaser: Phaser,
    ship_x: float,
    ship_y: float,
    ship_angle: int,
    targets_ships: list,     # list of Ship objects (opponents + self not checked)
    targets_torps: list,     # list of Torpedo objects (all active)
    planet_active: bool,
) -> tuple[list, list]:
    """
    Cast the phaser ray and return (ships_hit, torps_hit).

    The ray steps pixel-by-pixel; hit detection at every PHASER_TO_OBJ_RANGE px.
    Modifies phaser.end_x/.end_y to record where the ray stopped.
    Returns lists of (ship, damage) and (torp,) tuples for the caller to apply.
    """
    dx = T.cos_fp(ship_angle) / 32767.0   # unit direction vector
    dy = T.sin_fp(ship_angle) / 32767.0

    ships_hit = []
    torps_hit  = []

    end_x = ship_x
    end_y = ship_y
    hit_something = False

    for step in range(PHASER_RANGE):
        rx = ship_x + dx * step
        ry = ship_y + dy * step

        end_x = rx
        end_y = ry

        # Skip dead zone around firing ship
        if step < PHASER_SKIP:
            continue

        # Check hits every PHASER_TO_OBJ_RANGE pixels
        if step % PHASER_TO_OBJ_RANGE != 0:
            continue

        # Check planet collision
        if planet_active:
            pd = math.hypot(rx - PLANET_X, ry - PLANET_Y)
            if pd <= PLANET_RANGE:
                hit_something = True
                break

        # Check torpedo hits
        for t in targets_torps:
            if not (t.active and not t.exploding):
                continue
            dist = math.hypot(rx - t.x, ry - t.y)
            if dist < PHASER_TO_OBJ_RANGE:
                torps_hit.append(t)
                hit_something = True
                break

        if hit_something:
            break

        # Check ship hits
        for ship in targets_ships:
            if not ship.alive:
                continue
            dist = math.hypot(rx - ship.x, ry - ship.y)
            if dist < PHASER_TO_OBJ_RANGE:
                ships_hit.append(ship)
                hit_something = True
                break

        if hit_something:
            break

    phaser.end_x = end_x
    phaser.end_y = end_y
    phaser.hit = hit_something
    return ships_hit, torps_hit


def draw_phaser(surface, phaser: Phaser) -> None:
    """Draw the phaser ray if it is still visible (timer > PHASER_ERASE)."""
    if not phaser.active:
        return
    if phaser.timer <= (PHASER_DELAY - PHASER_ERASE):
        return

    import pygame
    sx = int(phaser.start_x)
    sy = int(phaser.start_y) * Y_SCALE
    ex = int(phaser.end_x)
    ey = int(phaser.end_y) * Y_SCALE
    pygame.draw.line(surface, WHITE, (sx, sy), (ex, ey), 1)
