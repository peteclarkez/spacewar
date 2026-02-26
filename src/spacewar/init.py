"""init.py — game object dataclasses and state initialisation.

Mirrors INIT.ASM.  The ASM stores all object fields as parallel arrays
(XDIS[], YDIS[], XVEL[], …) indexed by object number.  Here we use
dataclasses for clarity while keeping exactly the same field names.

Object table layout (16 slots):
  0        — Enterprise ship
  1-7      — Enterprise torpedoes
  8        — Klingon ship
  9-15     — Klingon torpedoes
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .constants import (
    EFLG_ACTIVE, EFLG_INACTIVE, PHASER_IDLE,
    ENT_START_X, ENT_START_Y, ENT_START_ANGLE,
    KLN_START_X, KLN_START_Y, KLN_START_ANGLE,
    STARTING_SHIELDS, STARTING_ENERGY,
    NUM_OBJECTS, ENT_OBJ, KLN_OBJ,
    MODE_ATTRACT,
)


# ---------------------------------------------------------------------------
# GameObject — mirrors per-slot ASM parallel arrays
# ---------------------------------------------------------------------------

@dataclass
class GameObject:
    """One entry in the 16-slot object table.

    Field names mirror ASM variable prefixes (XDIS→x, XVEL→vx, etc.).
    """
    # Position — 32-bit fixed-point: integer word + fractional word
    x: int = 0          # XDIS — virtual x coordinate (0..VIRTUAL_W-1)
    y: int = 0          # YDIS — virtual y coordinate (0..VIRTUAL_H-1)
    x_frac: int = 0     # XDISL — fractional position (unsigned 0..65535)
    y_frac: int = 0     # YDISL

    # Velocity — 32-bit fixed-point
    vx: int = 0         # XVEL — integer velocity (signed, clamped ±MAX_X_VEL)
    vy: int = 0         # YVEL
    vx_frac: int = 0    # XVELL — fractional velocity accumulator (unsigned)
    vy_frac: int = 0    # YVELL

    # Last-rendered state (used to erase the sprite before redrawing)
    x_drawn: int = 0    # PHX equivalent for ships; last draw x
    y_drawn: int = 0    # last draw y
    angle_drawn: int = 0  # last draw angle

    # Orientation
    angle: int = 0      # ANGLE — 0..255 (256 steps = full circle)
    rotate: int = 0     # ROTATE — signed delta applied each tick (±ROTATE_RATE)

    # State flags
    flags: int = 0      # FLAGS — BIT0=thrusting, BIT1=cloaking
    fire: int = 0       # FIRE — BIT0=torp debounce, BIT1=hyper debounce

    # Energy / damage
    shields: int = 0    # SHLDS — signed byte; death when < 0
    energy: int = 0     # ENRGY — dilithium/torpedo energy; max 127

    # Object lifecycle
    eflg: int = 0       # EFLG — 0=inactive, 1=active, -1=exploding
    uflg: int = 0       # UFLG — BIT0=redraw needed
    exps: int = 0       # EXPS — explosion frame counter (0=done)

    # Phaser state machine
    phaser_state: int = PHASER_IDLE   # PHST — 255=idle, counts down to 0
    phaser_count: int = 0             # PHCT — saved ray length for erase pass
    phaser_x: int = 0                 # PHX — saved ray origin x
    phaser_y: int = 0                 # PHY — saved ray origin y
    phaser_angle: int = 0             # PHA — saved ray angle


# ---------------------------------------------------------------------------
# HyperParticle — visual-only, used during hyperspace animation
# ---------------------------------------------------------------------------

@dataclass
class HyperParticle:
    """One scatter particle for hyperspace jump animation."""
    x: float = 0.0
    y: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    active: bool = False


# ---------------------------------------------------------------------------
# GameState — the entire mutable game world
# ---------------------------------------------------------------------------

@dataclass
class GameState:
    """All mutable global game state.

    Mirrors the ASM's module-level variables spread across multiple .ASM files.
    """
    # 16-slot object table
    objects: list[GameObject] = field(default_factory=lambda: [GameObject() for _ in range(NUM_OBJECTS)])

    # Master tick counter — 8-bit wrap (0..255); all timing gates off this
    blink: int = 0

    # BIT0=planet visible/collision, BIT1=gravity active  (PLANET.EQU)
    planet_enable: int = 0

    # Planet animation frame (0..15)
    planet_state: int = 0

    # Sound state
    sound_flag: int = 0       # Active sound bitmask (SOUND.EQU flags)
    sound_enable: bool = True  # F8 toggle
    sound_state: int = 0      # Phaser ramp counter

    # Robot AI enable flags (BIT0=Enterprise robot, BIT1=Klingon robot)
    auto_flag: int = 0

    # Pause
    pause_enable: bool = False

    # Function key debounce bitmask (F1-F8 → bits 0-7)
    function_flags: int = 0

    # Hyperspace animation counters (0=not in hyper, 1-64=animation tick)
    hyper_ent_flag: int = 0
    hyper_kln_flag: int = 0

    # Hyperspace destination (virtual coords), chosen at jump activation
    hyper_ent_dest_x: int = 0
    hyper_ent_dest_y: int = 0
    hyper_kln_dest_x: int = 0
    hyper_kln_dest_y: int = 0

    # 64 hyperspace particles: 0-31=Enterprise, 32-63=Klingon
    hyper_particles: list[HyperParticle] = field(
        default_factory=lambda: [HyperParticle() for _ in range(64)]
    )

    # Scores
    enterprise_score: int = 0
    klingon_score: int = 0

    # Score display — letter_flag BIT0=left-S visible, BIT1=right-S visible
    letter_flag: int = 0

    # Game mode
    game_mode: int = MODE_ATTRACT

    # Pre-generated star positions (list of (x, y) tuples)
    star_positions: list[tuple[int, int]] = field(default_factory=list)

    # 6-byte PRNG state buffer (Jim Butterfield routine, STARS.ASM)
    rng_state: list[int] = field(default_factory=lambda: [0] * 6)

    # --altkeys: replace right-player numpad controls with UIO/JKL/M,. layout
    alt_keys: bool = False


# ---------------------------------------------------------------------------
# Initialisation helpers
# ---------------------------------------------------------------------------

def _reset_ship(obj: GameObject, x: int, y: int, angle: int) -> None:
    """Reset a ship object to its starting state.  Mirrors INIT.ASM init_ship."""
    obj.x = x
    obj.y = y
    obj.x_frac = 0
    obj.y_frac = 0
    obj.vx = 0
    obj.vy = 0
    obj.vx_frac = 0
    obj.vy_frac = 0
    obj.angle = angle
    obj.rotate = 0
    obj.flags = 0
    obj.fire = 0
    obj.shields = STARTING_SHIELDS
    obj.energy = STARTING_ENERGY
    obj.eflg = EFLG_ACTIVE
    obj.uflg = 0
    obj.exps = 0
    obj.phaser_state = PHASER_IDLE
    obj.phaser_count = 0
    obj.phaser_x = 0
    obj.phaser_y = 0
    obj.phaser_angle = 0
    obj.x_drawn = x
    obj.y_drawn = y
    obj.angle_drawn = angle


def _reset_torpedo(obj: GameObject) -> None:
    """Reset a torpedo slot to inactive.  Mirrors INIT.ASM init_torp."""
    obj.x = 0
    obj.y = 0
    obj.x_frac = 0
    obj.y_frac = 0
    obj.vx = 0
    obj.vy = 0
    obj.vx_frac = 0
    obj.vy_frac = 0
    obj.angle = 0
    obj.rotate = 0
    obj.flags = 0
    obj.fire = 0
    obj.shields = 0
    obj.energy = 0
    obj.eflg = EFLG_INACTIVE
    obj.uflg = 0
    obj.exps = 0
    obj.phaser_state = PHASER_IDLE


def reset_game_objects(state: GameState) -> None:
    """Re-initialise all 16 object slots to starting conditions.

    Also clears hyperspace/explosion particle state so no stale visual
    artefacts carry across games.

    Mirrors INIT.ASM — called at the start of each new game and after death.
    """
    _reset_ship(state.objects[ENT_OBJ], ENT_START_X, ENT_START_Y, ENT_START_ANGLE)
    _reset_ship(state.objects[KLN_OBJ], KLN_START_X, KLN_START_Y, KLN_START_ANGLE)
    for i in range(1, 8):
        _reset_torpedo(state.objects[i])
    for i in range(9, 16):
        _reset_torpedo(state.objects[i])
    # Clear particle animation state
    state.hyper_ent_flag = 0
    state.hyper_kln_flag = 0
    for p in state.hyper_particles:
        p.active = False


def new_game_state() -> GameState:
    """Create a fresh GameState ready for attract mode."""
    state = GameState()
    reset_game_objects(state)
    return state
