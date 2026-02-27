"""
Core physics engine: velocity integration, gravity, screen wrapping,
velocity capping, torpedo spawning, and hyperspace / explosion particles.

Coordinate system
-----------------
All positions are in virtual 640×200 space.
Velocities are floats in virtual pixels per tick, capped at ±MAX_VELOCITY.
The 16.16 fixed-point representation of the original is emulated with floats:
  v_fp (integer) → v_float = v_fp / FRAC  (FRAC = 65536)
"""

from __future__ import annotations
import math
import random
from dataclasses import dataclass, field

from spacewar.constants import (
    VIRTUAL_W, VIRTUAL_H, WRAP_FACTOR,
    MAX_VELOCITY, FRAC,
    PLANET_X, PLANET_Y,
    HYPER_DURATION, HYPER_PHASE, HYPER_PARTICLES,
    SHIP_EXPLOSION_TICKS,
)
from spacewar import trig as T


# ── Wrap ──────────────────────────────────────────────────────────────────────

def wrap_x(x: float) -> float:
    """Apply horizontal screen wrap with WRAP_FACTOR overlap."""
    span = VIRTUAL_W - 2 * WRAP_FACTOR
    if x < WRAP_FACTOR:
        x += span
    elif x >= VIRTUAL_W - WRAP_FACTOR:
        x -= span
    return x


def wrap_y(y: float) -> float:
    """Apply vertical screen wrap with WRAP_FACTOR overlap."""
    span = VIRTUAL_H - 2 * WRAP_FACTOR
    if y < WRAP_FACTOR:
        y += span
    elif y >= VIRTUAL_H - WRAP_FACTOR:
        y -= span
    return y


def wrap(x: float, y: float) -> tuple[float, float]:
    """Wrap both axes."""
    return wrap_x(x), wrap_y(y)


# ── Velocity cap ──────────────────────────────────────────────────────────────

def cap_velocity(v: float) -> float:
    """Clamp velocity to [-MAX_VELOCITY, +MAX_VELOCITY]."""
    return max(-MAX_VELOCITY, min(MAX_VELOCITY, v))


# ── Gravity ───────────────────────────────────────────────────────────────────

def gravity_delta(x: float, y: float) -> tuple[float, float]:
    """
    "Bowl gravity": linear pull toward planet centre.
    Original ASM: accel = -(pos - PLANET_POS) << 3   (in fixed-point units).
    Converted to float: accel = -(pos - PLANET_POS) * 8 / FRAC
    """
    ax = -(x - PLANET_X) * 8 / FRAC
    ay = -(y - PLANET_Y) * 8 / FRAC
    return ax, ay


# ── Integrate position ────────────────────────────────────────────────────────

def integrate(x: float, y: float, vx: float, vy: float) -> tuple[float, float]:
    """Advance position by velocity, then wrap."""
    return wrap(x + vx, y + vy)


# ── Distance helper ───────────────────────────────────────────────────────────

def distance(ax: float, ay: float, bx: float, by: float) -> float:
    """Euclidean distance between two points in virtual space."""
    return math.hypot(ax - bx, ay - by)


# ── Particle dataclass (hyperspace / death explosion) ─────────────────────────

@dataclass
class Particle:
    x: float = 0.0
    y: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    active: bool = False


@dataclass
class ParticleSystem:
    """
    32-particle system shared by hyperspace jumps and death explosions.

    A death explosion sets is_death=True and uses only phase 1 (expansion).
    A hyperspace jump uses both phases and teleports the ship on completion.
    """
    particles: list[Particle] = field(default_factory=lambda: [Particle() for _ in range(HYPER_PARTICLES)])
    tick: int = 0          # current animation tick (0 = inactive)
    is_death: bool = False # True → death explosion (no contraction, no teleport)
    dest_x: float = 0.0   # hyperspace destination X
    dest_y: float = 0.0   # hyperspace destination Y
    src_x:  float = 0.0   # origin of the jump
    src_y:  float = 0.0

    @property
    def active(self) -> bool:
        return self.tick > 0

    @property
    def done(self) -> bool:
        return self.tick > HYPER_DURATION

    def start_hyperspace(self, ship_x: float, ship_y: float,
                          dest_x: float, dest_y: float) -> None:
        """Launch a hyperspace jump from (ship_x, ship_y) to (dest_x, dest_y)."""
        self.tick = 1
        self.is_death = False
        self.src_x = ship_x
        self.src_y = ship_y
        self.dest_x = dest_x
        self.dest_y = dest_y
        self._scatter_particles(ship_x, ship_y, dest_x, dest_y)

    def start_death(self, ship_x: float, ship_y: float,
                    ship_vx: float = 0.0, ship_vy: float = 0.0) -> None:
        """Launch a death explosion centred on the ship."""
        self.tick = 1
        self.is_death = True
        self.src_x = ship_x
        self.src_y = ship_y
        self.dest_x = ship_x
        self.dest_y = ship_y
        self._scatter_particles(ship_x, ship_y, ship_x, ship_y, ship_vx, ship_vy)

    def _scatter_particles(self, ox: float, oy: float,
                            dx: float, dy: float,
                            extra_vx: float = 0.0,
                            extra_vy: float = 0.0) -> None:
        """Initialise particles with radial scatter + translational drift."""
        transit_vx = (dx - ox) / HYPER_DURATION
        transit_vy = (dy - oy) / HYPER_DURATION
        for p in self.particles:
            p.x = ox
            p.y = oy
            # Radial scatter component
            angle = random.random() * 2 * math.pi
            speed = random.uniform(0.3, 1.5)
            p.vx = math.cos(angle) * speed + transit_vx + extra_vx * 0.3
            p.vy = math.sin(angle) * speed + transit_vy + extra_vy * 0.3
            p.active = True

    def update(self) -> None:
        """Advance the animation by one tick."""
        if not self.active:
            return

        # Phase transition at HYPER_PHASE+1 (only for real hyperspace)
        if self.tick == HYPER_PHASE + 1 and not self.is_death:
            # Redirect particles to converge on destination
            for p in self.particles:
                if p.active:
                    remaining = HYPER_PHASE
                    p.vx = (self.dest_x - p.x) / remaining
                    p.vy = (self.dest_y - p.y) / remaining

        # Move particles
        for p in self.particles:
            if p.active:
                p.x, p.y = wrap(p.x + p.vx, p.y + p.vy)

        self.tick += 1

        if self.done:
            for p in self.particles:
                p.active = False

    def draw(self, surface, colour: tuple, y_scale: int = 2) -> None:
        """Draw all active particles."""
        for p in self.particles:
            if p.active:
                sx = int(p.x)
                sy = int(p.y) * y_scale
                surface.set_at((sx, sy), colour)
