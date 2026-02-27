"""
Photon torpedo — lifecycle, physics, and rendering helpers.

Each ship maintains a pool of MAX_TORPS (7) torpedo slots.
A torpedo's "fuel" (energy) ticks down; when exhausted it explodes.
Gravity affects torpedoes identically to ships.
"""

from __future__ import annotations
from dataclasses import dataclass

from spacewar.constants import (
    PHOTON_ENERGY, PHOTON_TIME, MAX_VELOCITY,
    FIRE_SCALE, TORP_SPAWN_SHIFT, MAX_TORPS,
    PLAYER_ENT,
)
from spacewar import trig as T
from spacewar.physics import cap_velocity, gravity_delta, integrate, wrap


@dataclass
class Torpedo:
    """A single torpedo in the pool."""
    active:   bool  = False
    x:        float = 0.0
    y:        float = 0.0
    vx:       float = 0.0
    vy:       float = 0.0
    angle:    int   = 0      # 256-unit angle at launch
    energy:   int   = 0      # countdown; 0 → explode
    owner:    int   = PLAYER_ENT   # PLAYER_ENT or PLAYER_KLN
    exploding: bool = False  # explosion animation active
    exptick:  int   = 0      # explosion animation counter

    def reset(self) -> None:
        self.active = self.exploding = False
        self.x = self.y = self.vx = self.vy = 0.0
        self.energy = self.angle = self.exptick = 0

    def launch(self, ship_x: float, ship_y: float,
               ship_vx: float, ship_vy: float,
               ship_angle: int, owner: int) -> None:
        """
        Launch the torpedo from the ship.
        Velocity = ship_vel + (cos/sin * 4).
        Spawn offset keeps it outside SHIP_TO_TORP_RANGE.
        """
        ox, oy = T.spawn_offset(ship_angle, TORP_SPAWN_SHIFT)
        tvx, tvy = T.torpedo_velocity(ship_angle, FIRE_SCALE)

        self.x      = ship_x + ox
        self.y      = ship_y + oy
        self.vx     = cap_velocity(ship_vx + tvx)
        self.vy     = cap_velocity(ship_vy + tvy)
        self.angle  = ship_angle
        self.energy = PHOTON_ENERGY
        self.owner  = owner
        self.active = True
        self.exploding = False
        self.exptick   = 0

    def update(self, gravity_on: bool, tick: int) -> None:
        """
        Advance torpedo physics and energy drain.
        tick: the global game tick (used to time energy drain).
        """
        if not self.active:
            return

        if self.exploding:
            self.exptick += 2
            if self.exptick > 64:
                self.active = self.exploding = False
            return

        # Gravity
        if gravity_on:
            ax, ay = gravity_delta(self.x, self.y)
            self.vx = cap_velocity(self.vx + ax)
            self.vy = cap_velocity(self.vy + ay)

        # Move
        self.x, self.y = integrate(self.x, self.y, self.vx, self.vy)

        # Energy drain every PHOTON_TIME ticks
        if tick % PHOTON_TIME == 0:
            self.energy -= 1
            if self.energy <= 0:
                self.begin_explosion()

    def begin_explosion(self) -> None:
        self.exploding = True
        self.exptick   = 0
        # Keep active=True so explosion draws; set to False when anim ends

    def begin_planet_hit(self) -> None:
        self.begin_explosion()

    @property
    def is_alive(self) -> bool:
        return self.active and not self.exploding


class TorpedoPool:
    """Manages up to MAX_TORPS torpedoes for one ship."""

    def __init__(self, owner: int) -> None:
        self.owner = owner
        self.slots: list[Torpedo] = [Torpedo() for _ in range(MAX_TORPS)]

    def reset(self) -> None:
        for t in self.slots:
            t.reset()

    def fire(self, ship_x: float, ship_y: float,
             ship_vx: float, ship_vy: float,
             ship_angle: int) -> bool:
        """
        Attempt to fire a torpedo. Returns True if a slot was free.
        Blocked when all 7 slots are active.
        """
        for t in self.slots:
            if not t.active:
                t.launch(ship_x, ship_y, ship_vx, ship_vy, ship_angle, self.owner)
                return True
        return False

    def update(self, gravity_on: bool, tick: int) -> None:
        for t in self.slots:
            t.update(gravity_on, tick)

    def active_torpedoes(self) -> list[Torpedo]:
        return [t for t in self.slots if t.active and not t.exploding]

    def draw(self, surface, neon: bool = False) -> None:
        """Draw all active (non-exploding) torpedoes."""
        from spacewar import sprites as SP
        from spacewar.constants import Y_SCALE, NEON_ETORP_GLOW, NEON_KTORP_GLOW

        for t in self.slots:
            if not t.active:
                continue
            if t.exploding:
                _draw_torp_explosion(surface, t)
                continue
            surf = SP.get_torp_frame(self.owner, t.angle)
            if neon:
                glow = NEON_ETORP_GLOW if self.owner == 0 else NEON_KTORP_GLOW
                SP.draw_neon_sprite(surface, surf, t.x, t.y, glow)
            else:
                SP.draw_sprite_centered(surface, surf, t.x, t.y)


def _draw_torp_explosion(surface, t: Torpedo) -> None:
    """Small expanding circle explosion for a torpedo."""
    from spacewar.constants import Y_SCALE, WHITE
    import pygame
    sx = int(t.x)
    sy = int(t.y) * Y_SCALE
    radius = (t.exptick // 8) + 1
    if radius > 0:
        pygame.draw.circle(surface, WHITE, (sx, sy), radius, 1)
