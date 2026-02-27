"""
Ship class — holds all per-ship state and handles physics + energy timers.

Designed to be pure Python (no pygame dependency) so it's fully unit-testable.
"""

from __future__ import annotations
from dataclasses import dataclass, field

from spacewar.constants import (
    STARTING_SHIELDS, STARTING_ENERGY, MAX_ENERGY,
    DILITHIUM_TIME, IMPULSE_TIME, CLOAK_TIME, SWAP_TIME,
    HYPERSPACE_ENERGY, PHASER_FIRE_ENERGY, PHOTON_LAUNCH_ENERGY,
    MAX_VELOCITY, ROTATE_RATE, ACCEL_SCALE, FRAC,
    HYPER_DURATION, SHIP_EXPLOSION_TICKS,
    ENT_START_X, ENT_START_Y, ENT_START_A,
    KLN_START_X, KLN_START_Y, KLN_START_A,
    PLAYER_ENT, PLAYER_KLN,
)
from spacewar import trig as T
from spacewar.physics import (
    cap_velocity, gravity_delta, integrate,
    ParticleSystem,
)


@dataclass
class Ship:
    """
    All mutable state for one ship.

    Coordinates are in virtual 640×200 space.
    Velocities are floats in [-MAX_VELOCITY, +MAX_VELOCITY].
    """

    player:    int    = PLAYER_ENT   # 0=Enterprise, 1=Klingon

    # ── Kinematics ────────────────────────────────────────────────────────────
    x:   float = 0.0
    y:   float = 0.0
    vx:  float = 0.0
    vy:  float = 0.0
    angle: int = 0      # 256-unit angle system

    # ── Energy / shields ──────────────────────────────────────────────────────
    shields: int = STARTING_SHIELDS
    energy:  int = STARTING_ENERGY

    # ── Status flags ──────────────────────────────────────────────────────────
    alive:    bool = True
    cloaked:  bool = False
    dead:     bool = False   # True once destroyed (explosion still running)

    # ── Weapon cooldown counters ──────────────────────────────────────────────
    phaser_timer:   int = 0    # counts down to 0; can fire phasers when 0
    torp_debounce:  bool = False  # True if torpedo key held from last press
    hyper_debounce: bool = False  # True if hyperspace key held from last press

    # ── Energy timer counters ─────────────────────────────────────────────────
    impulse_timer:  int = 0
    cloak_timer:    int = 0
    energy_timer:   int = 0   # counts to DILITHIUM_TIME for recharge
    swap_timer:     int = 0   # counts to SWAP_TIME for S↔E transfer

    # ── Hyperspace / death animation ──────────────────────────────────────────
    particles: ParticleSystem = field(default_factory=ParticleSystem)

    # ── Score (persistent across games) ───────────────────────────────────────
    score: int = 0

    # ─────────────────────────────────────────────────────────────────────────

    @classmethod
    def enterprise(cls) -> "Ship":
        s = cls(player=PLAYER_ENT)
        s.reset()
        return s

    @classmethod
    def klingon(cls) -> "Ship":
        s = cls(player=PLAYER_KLN)
        s.reset()
        return s

    def reset(self) -> None:
        """Reset ship to its game-start state (score is preserved)."""
        if self.player == PLAYER_ENT:
            self.x, self.y, self.angle = ENT_START_X, ENT_START_Y, ENT_START_A
        else:
            self.x, self.y, self.angle = KLN_START_X, KLN_START_Y, KLN_START_A

        self.vx = self.vy = 0.0
        self.shields  = STARTING_SHIELDS
        self.energy   = STARTING_ENERGY
        self.alive    = True
        self.cloaked  = False
        self.dead     = False

        self.phaser_timer   = 0
        self.torp_debounce  = False
        self.hyper_debounce = False
        self.impulse_timer  = 0
        self.cloak_timer    = 0
        self.energy_timer   = 0
        self.swap_timer     = 0

        if self.particles.active:
            self.particles.tick = HYPER_DURATION + 1   # force done

    # ── Per-tick physics update ───────────────────────────────────────────────

    def apply_gravity(self) -> None:
        """Add bowl-gravity acceleration toward planet."""
        ax, ay = gravity_delta(self.x, self.y)
        self.vx = cap_velocity(self.vx + ax)
        self.vy = cap_velocity(self.vy + ay)

    def apply_thrust(self) -> None:
        """
        Apply one tick of thrust in the ship's facing direction.
        Costs 1 E-energy every IMPULSE_TIME ticks.
        """
        if self.energy <= 0:
            return
        ax, ay = T.thrust_components(self.angle, ACCEL_SCALE)
        nvx = self.vx + ax
        nvy = self.vy + ay
        # Only apply if it doesn't exceed the velocity cap
        if abs(nvx) <= MAX_VELOCITY:
            self.vx = nvx
        if abs(nvy) <= MAX_VELOCITY:
            self.vy = nvy

        self.impulse_timer += 1
        if self.impulse_timer >= IMPULSE_TIME:
            self.impulse_timer = 0
            self.energy -= 1

    def rotate_left(self) -> None:
        self.angle = (self.angle - ROTATE_RATE) % 256

    def rotate_right(self) -> None:
        self.angle = (self.angle + ROTATE_RATE) % 256

    def apply_cloak(self) -> None:
        """Activate cloaking (called while cloak key is held)."""
        if self.energy <= 0:
            self.cloaked = False
            return
        self.cloaked = True
        self.cloak_timer += 1
        if self.cloak_timer >= CLOAK_TIME:
            self.cloak_timer = 0
            self.energy -= 1

    def deactivate_cloak(self) -> None:
        self.cloaked = False
        self.cloak_timer = 0

    def tick_energy(self) -> None:
        """Advance energy recharge timer; add +1 E if due."""
        self.energy_timer += 1
        if self.energy_timer >= DILITHIUM_TIME:
            self.energy_timer = 0
            if self.energy < MAX_ENERGY:
                self.energy += 1

    def tick_timers(self) -> None:
        """Advance all cooldown timers that should tick every game step."""
        if self.phaser_timer > 0:
            self.phaser_timer -= 1

    def can_fire_phaser(self) -> bool:
        return self.phaser_timer == 0 and self.energy >= PHASER_FIRE_ENERGY

    def fire_phaser(self) -> None:
        """Deduct energy and start phaser cooldown."""
        self.energy -= PHASER_FIRE_ENERGY
        from spacewar.constants import PHASER_DELAY
        self.phaser_timer = PHASER_DELAY

    def can_fire_torpedo(self, torp_key_down: bool) -> bool:
        """Return True if a torpedo can be launched (debounce logic)."""
        if torp_key_down:
            if not self.torp_debounce and self.energy >= PHOTON_LAUNCH_ENERGY:
                return True
        else:
            self.torp_debounce = False
        return False

    def consume_torpedo_energy(self) -> None:
        self.energy -= PHOTON_LAUNCH_ENERGY
        self.torp_debounce = True

    def can_hyperspace(self, hyper_key_down: bool) -> bool:
        if hyper_key_down:
            if not self.hyper_debounce and self.energy >= HYPERSPACE_ENERGY:
                return True
        else:
            self.hyper_debounce = False
        return False

    def consume_hyperspace_energy(self) -> None:
        self.energy -= HYPERSPACE_ENERGY
        self.hyper_debounce = True

    def shields_to_energy(self) -> None:
        """Transfer 1 unit from S → E (rate-limited by swap_timer)."""
        self.swap_timer += 1
        if self.swap_timer >= SWAP_TIME:
            self.swap_timer = 0
            if self.shields > 0 and self.energy < MAX_ENERGY:
                self.shields -= 1
                self.energy  += 1

    def energy_to_shields(self) -> None:
        """Transfer 1 unit from E → S (rate-limited by swap_timer)."""
        self.swap_timer += 1
        if self.swap_timer >= SWAP_TIME:
            self.swap_timer = 0
            if self.energy > 0:
                self.energy  -= 1
                self.shields += 1

    def apply_damage(self, amount: int) -> bool:
        """
        Apply shield damage. Returns True if ship is destroyed.
        A ship dies when shields go negative (signed byte semantics).
        """
        self.shields -= amount
        if self.shields < 0:
            self.dead = True
            self.alive = False
            return True
        return False

    def move(self, gravity_on: bool) -> None:
        """Integrate position; optionally apply gravity."""
        if gravity_on:
            self.apply_gravity()
        self.x, self.y = integrate(self.x, self.y, self.vx, self.vy)

    @property
    def is_exploding(self) -> bool:
        return self.particles.active

    @property
    def shield_warning(self) -> bool:
        from spacewar.constants import LOW_SHIELD_LIMIT
        return self.shields < LOW_SHIELD_LIMIT
