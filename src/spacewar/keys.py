"""keys.py — keyboard input and robot AI.

Mirrors KEYS.ASM + KEYS.EQU + robot AI sections of MAIN.ASM.

Key layout (from KEYS.EQU):
  Enterprise:
    Q = phasers        W = cloak          E = photon torpedo
    A = rotate CCW     S = impulse (thrust) D = rotate CW
    Z = shields→energy  X = hyperspace    C = energy→shields

  Klingon (numpad):
    7 = phasers        8 = cloak          9 = photon torpedo
    4 = rotate CCW     5 = impulse        6 = rotate CW
    1 = shields→energy  2 = hyperspace    3 = energy→shields

  Function keys:
    F1 = exit / attract    F2 = start game
    F3 = Enterprise robot  F4 = Klingon robot
    F5 = planet toggle     F6 = gravity toggle
    F7 = pause toggle      F8 = sound toggle

Robot AI:
  Enterprise (LEFT robot) — fires phasers only; random impulse/hyper
  Klingon    (RIGHT robot) — aims at Enterprise; fires torps/phasers; random impulse/hyper

Public API
----------
KeyState — dataclass for key tracking
update_key_state(key_state)                   — call once per frame
process_enterprise_keys(state, key_state, surface)
process_klingon_keys(state, key_state, surface)
process_function_keys(state, key_state) -> int  — returns new game mode
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pygame

from .constants import (
    ENT_OBJ, KLN_OBJ,
    EFLG_ACTIVE, EFLG_EXPLODING, EFLG_INACTIVE,
    THRUST_BIT, CLOAK_BIT, TORP_FIRE_BIT, HYPER_FIRE_BIT,
    ROTATE_RATE,
    STARTING_SHIELDS, STARTING_ENERGY,
    SWAP_TIME,
    AUTO_ENT_BIT, AUTO_KLN_BIT,
    PLANET_BIT, GRAVITY_BIT,
    PHASER_RANGE,
    PROB_IMPULSE, PROB_PHOTON, PROB_HYPER,
    HYPERSPACE_ENERGY,
    HYPER_SOUND, HYPER_DURATION,
    HYPER_PARTICLES,
    MODE_ATTRACT, MODE_PLAY,
    WRAP_FACTOR, VIRTUAL_W, VIRTUAL_H,
)
from .trig import atan_approx
from .stars import random_next
from .torpedo import fire_enterprise_torpedo, fire_klingon_torpedo
from .init import GameState, HyperParticle


# ---------------------------------------------------------------------------
# KeyState
# ---------------------------------------------------------------------------

@dataclass
class KeyState:
    """Tracks current, just-pressed, and just-released keys."""
    pressed: dict[int, bool] = field(default_factory=dict)
    just_pressed: dict[int, bool] = field(default_factory=dict)
    just_released: dict[int, bool] = field(default_factory=dict)


# All pygame.K_* constants used anywhere in the game.
# We iterate over these explicitly so that just_pressed/just_released are
# keyed by K_* constants (e.g. K_F2=282), matching all downstream lookups.
# pygame.key.get_pressed() returns a sequence indexed by scancode, but
# K_* constants are keycodes — iterating range(len(current)) would store
# state at scancode indices and lookups via K_* would always miss.
_GAME_KEYS = [
    # Enterprise controls
    pygame.K_q, pygame.K_w, pygame.K_e,
    pygame.K_a, pygame.K_s, pygame.K_d,
    pygame.K_z, pygame.K_x, pygame.K_c,
    # Klingon controls (numpad)
    pygame.K_KP7, pygame.K_KP8, pygame.K_KP9,
    pygame.K_KP4, pygame.K_KP5, pygame.K_KP6,
    pygame.K_KP1, pygame.K_KP2, pygame.K_KP3,
    # Function keys
    pygame.K_F1, pygame.K_F2, pygame.K_F3, pygame.K_F4,
    pygame.K_F5, pygame.K_F6, pygame.K_F7, pygame.K_F8,
    # Misc
    pygame.K_ESCAPE,
]


def update_key_state(key_state: KeyState) -> None:
    """Refresh KeyState from pygame's event queue snapshot.

    Must be called after pygame.event.pump() / event.get() each frame.
    """
    current = pygame.key.get_pressed()
    new_pressed: dict[int, bool] = {}
    just_pressed: dict[int, bool] = {}
    just_released: dict[int, bool] = {}

    for k in _GAME_KEYS:
        was = key_state.pressed.get(k, False)
        now = bool(current[k])
        new_pressed[k] = now
        if now and not was:
            just_pressed[k] = True
        if was and not now:
            just_released[k] = True

    key_state.pressed = new_pressed
    key_state.just_pressed = just_pressed
    key_state.just_released = just_released


# ---------------------------------------------------------------------------
# Hyperspace helper
# ---------------------------------------------------------------------------

def _activate_hyperspace(state: GameState, ship_idx: int) -> None:
    """Begin hyperspace jump animation for ship_idx.

    Mirrors the hyperspace initiation in MAIN.ASM:
    - Deduct HYPERSPACE_ENERGY
    - Launch 32 scatter particles
    - Mark ship as exploding (hidden during travel)
    - Set hyper_*_flag to 1
    """
    ship = state.objects[ship_idx]
    if ship.energy < HYPERSPACE_ENERGY:
        return
    if ship.fire & HYPER_FIRE_BIT:
        return

    ship.energy -= HYPERSPACE_ENERGY
    ship.fire |= HYPER_FIRE_BIT
    ship.eflg = EFLG_EXPLODING   # hide ship during transit

    # Launch scatter particles
    import math as _math
    import random as _random
    particle_start = 0 if ship_idx == ENT_OBJ else 32
    for i in range(HYPER_PARTICLES):
        p = state.hyper_particles[particle_start + i]
        a = (i / HYPER_PARTICLES) * 2 * _math.pi
        speed = _random.uniform(0.5, 2.5)
        p.x = float(ship.x)
        p.y = float(ship.y)
        p.vx = _math.cos(a) * speed
        p.vy = _math.sin(a) * speed
        p.active = True

    if ship_idx == ENT_OBJ:
        state.hyper_ent_flag = 1
        state.sound_flag |= HYPER_SOUND
    else:
        state.hyper_kln_flag = 1
        state.sound_flag |= HYPER_SOUND


# ---------------------------------------------------------------------------
# Energy transfer helper
# ---------------------------------------------------------------------------

def _transfer_shields_to_energy(ship, blink: int) -> None:
    """Transfer 1 point S→E every SWAP_TIME ticks."""
    if (blink & (SWAP_TIME - 1)) != 0:
        return
    if ship.shields > 0 and ship.energy < STARTING_ENERGY:
        ship.shields -= 1
        ship.energy += 1


def _transfer_energy_to_shields(ship, blink: int) -> None:
    """Transfer 1 point E→S every SWAP_TIME ticks."""
    if (blink & (SWAP_TIME - 1)) != 0:
        return
    if ship.energy > 0 and ship.shields < STARTING_SHIELDS:
        ship.energy -= 1
        ship.shields += 1


# ---------------------------------------------------------------------------
# Enterprise key processing
# ---------------------------------------------------------------------------

def process_enterprise_keys(
    state: GameState,
    key_state: KeyState,
    surface=None,
) -> None:
    """Handle Enterprise controls or route to robot AI.

    Mirrors ent_keys in KEYS.ASM.
    """
    if state.auto_flag & AUTO_ENT_BIT:
        _auto_enterprise(state, surface)
        return

    ship = state.objects[ENT_OBJ]
    if ship.eflg != EFLG_ACTIVE:
        return

    p = key_state.pressed

    # Rotation
    ship.rotate = 0
    if p.get(pygame.K_a):
        ship.rotate = -ROTATE_RATE
    elif p.get(pygame.K_d):
        ship.rotate = ROTATE_RATE

    # Thrust (impulse)
    if p.get(pygame.K_s):
        ship.flags |= THRUST_BIT
    else:
        ship.flags &= ~THRUST_BIT

    # Cloak
    if p.get(pygame.K_w):
        ship.flags |= CLOAK_BIT
    else:
        ship.flags &= ~CLOAK_BIT

    # Phaser
    if key_state.just_pressed.get(pygame.K_q):
        if surface is not None:
            from .phaser import fire_phaser_enterprise
            fire_phaser_enterprise(state, surface)

    # Photon torpedo
    if p.get(pygame.K_e):
        fire_enterprise_torpedo(state)
    else:
        ship.fire &= ~TORP_FIRE_BIT   # release debounce when key up

    # Hyperspace
    if key_state.just_pressed.get(pygame.K_x):
        _activate_hyperspace(state, ENT_OBJ)
    else:
        ship.fire &= ~HYPER_FIRE_BIT

    # Energy transfer
    if p.get(pygame.K_z):
        _transfer_shields_to_energy(ship, state.blink)
    if p.get(pygame.K_c):
        _transfer_energy_to_shields(ship, state.blink)


# ---------------------------------------------------------------------------
# Klingon key processing
# ---------------------------------------------------------------------------

def process_klingon_keys(
    state: GameState,
    key_state: KeyState,
    surface=None,
) -> None:
    """Handle Klingon controls or route to robot AI.

    Mirrors kln_keys in KEYS.ASM.
    """
    if state.auto_flag & AUTO_KLN_BIT:
        _auto_klingon(state, surface)
        return

    ship = state.objects[KLN_OBJ]
    if ship.eflg != EFLG_ACTIVE:
        return

    p = key_state.pressed

    # Rotation (numpad 4/6)
    ship.rotate = 0
    if p.get(pygame.K_KP4):
        ship.rotate = -ROTATE_RATE
    elif p.get(pygame.K_KP6):
        ship.rotate = ROTATE_RATE

    # Thrust (numpad 5)
    if p.get(pygame.K_KP5):
        ship.flags |= THRUST_BIT
    else:
        ship.flags &= ~THRUST_BIT

    # Cloak (numpad 8)
    if p.get(pygame.K_KP8):
        ship.flags |= CLOAK_BIT
    else:
        ship.flags &= ~CLOAK_BIT

    # Phaser (numpad 7)
    if key_state.just_pressed.get(pygame.K_KP7):
        if surface is not None:
            from .phaser import fire_phaser_klingon
            fire_phaser_klingon(state, surface)

    # Photon torpedo (numpad 9)
    if p.get(pygame.K_KP9):
        fire_klingon_torpedo(state)
    else:
        ship.fire &= ~TORP_FIRE_BIT

    # Hyperspace (numpad 2)
    if key_state.just_pressed.get(pygame.K_KP2):
        _activate_hyperspace(state, KLN_OBJ)
    else:
        ship.fire &= ~HYPER_FIRE_BIT

    # Energy transfer (numpad 1/3)
    if p.get(pygame.K_KP1):
        _transfer_shields_to_energy(ship, state.blink)
    if p.get(pygame.K_KP3):
        _transfer_energy_to_shields(ship, state.blink)


# ---------------------------------------------------------------------------
# Function key processing
# ---------------------------------------------------------------------------

def process_function_keys(state: GameState, key_state: KeyState) -> int:
    """Handle F1–F8 toggles.  Returns new game mode (may be unchanged).

    Mirrors function key handling split between KEYS.ASM and MAIN.ASM.
    Uses just_pressed so each press is handled once.
    """
    jp = key_state.just_pressed
    mode = state.game_mode

    if jp.get(pygame.K_F1):          # Attract / exit
        mode = MODE_ATTRACT

    if jp.get(pygame.K_F2):          # Start game
        from .init import reset_game_objects
        reset_game_objects(state)
        state.pause_enable = False
        mode = MODE_PLAY

    if jp.get(pygame.K_F3):          # Toggle Enterprise robot
        state.auto_flag ^= AUTO_ENT_BIT

    if jp.get(pygame.K_F4):          # Toggle Klingon robot
        state.auto_flag ^= AUTO_KLN_BIT

    if jp.get(pygame.K_F5):          # Toggle planet (BIT0)
        state.planet_enable ^= PLANET_BIT

    if jp.get(pygame.K_F6):          # Toggle gravity (BIT1)
        state.planet_enable ^= GRAVITY_BIT

    if jp.get(pygame.K_F7):          # Toggle pause
        state.pause_enable = not state.pause_enable

    if jp.get(pygame.K_F8):          # Toggle sound
        state.sound_enable = not state.sound_enable

    state.game_mode = mode
    return mode


# ---------------------------------------------------------------------------
# Robot AI — Enterprise (auto_ent)
# ---------------------------------------------------------------------------

def _auto_enterprise(state: GameState, surface=None) -> None:
    """Enterprise robot AI.  Mirrors auto_ent in MAIN.ASM.

    Strategy:
      1. Balance energy (S↔E toward equality)
      2. If energy=0: stop thrusting and phasers, return
      3. Scan Klingon objects for any within PHASER_RANGE on both axes
      4. If found: compute bearing, snap angle, fire phasers
      5. Random impulse (1/PROB_IMPULSE chance)
      6. Random hyperspace (1/PROB_HYPER chance)
    """
    ship = state.objects[ENT_OBJ]
    if ship.eflg != EFLG_ACTIVE:
        return

    # 1. Balance energy
    if ship.shields > ship.energy:
        _transfer_shields_to_energy(ship, state.blink)
    elif ship.energy > ship.shields:
        _transfer_energy_to_shields(ship, state.blink)

    # 2. Out of energy?
    if ship.energy <= 0:
        ship.flags &= ~THRUST_BIT
        return

    # 3. Scan Klingon side for targets in phaser range
    target_found = False
    for i in range(KLN_OBJ, 16):
        obj = state.objects[i]
        if obj.eflg != EFLG_ACTIVE:
            continue
        if abs(obj.x - ship.x) < PHASER_RANGE and abs(obj.y - ship.y) < PHASER_RANGE:
            # 4. Compute bearing and fire phasers
            dx = obj.x - ship.x
            dy = obj.y - ship.y
            ship.angle = atan_approx(dx, dy)
            if surface is not None:
                from .phaser import fire_phaser_enterprise
                fire_phaser_enterprise(state, surface)
            target_found = True
            break

    # 5. Random impulse
    if random_next(state.rng_state) % PROB_IMPULSE == 0:
        ship.flags |= THRUST_BIT
    else:
        ship.flags &= ~THRUST_BIT

    # 6. Random hyperspace
    if random_next(state.rng_state) % PROB_HYPER == 0:
        _activate_hyperspace(state, ENT_OBJ)


# ---------------------------------------------------------------------------
# Robot AI — Klingon (auto_kln)
# ---------------------------------------------------------------------------

def _auto_klingon(state: GameState, surface=None) -> None:
    """Klingon robot AI.  Mirrors auto_kln in MAIN.ASM.

    Strategy:
      1. Always aim at Enterprise (update angle every tick)
      2. Balance energy (S↔E toward equality)
      3. If energy=0: stop thrusting and photons, return
      4. Random fire check (1/PROB_PHOTON):
           if Enterprise within PHASER_RANGE: fire phasers
           else: fire photon torpedo
      5. Random impulse (1/PROB_IMPULSE)
      6. Random hyperspace (1/PROB_HYPER)
    """
    ship = state.objects[KLN_OBJ]
    if ship.eflg != EFLG_ACTIVE:
        return

    ent = state.objects[ENT_OBJ]

    # 1. Always aim at Enterprise
    if ent.eflg == EFLG_ACTIVE:
        dx = ent.x - ship.x
        dy = ent.y - ship.y
        ship.angle = atan_approx(dx, dy)

    # 2. Balance energy
    if ship.shields > ship.energy:
        _transfer_shields_to_energy(ship, state.blink)
    elif ship.energy > ship.shields:
        _transfer_energy_to_shields(ship, state.blink)

    # 3. Out of energy?
    if ship.energy <= 0:
        ship.flags &= ~THRUST_BIT
        return

    # 4. Random fire
    if random_next(state.rng_state) % PROB_PHOTON == 0:
        if (ent.eflg == EFLG_ACTIVE
                and abs(ent.x - ship.x) < PHASER_RANGE
                and abs(ent.y - ship.y) < PHASER_RANGE):
            if surface is not None:
                from .phaser import fire_phaser_klingon
                fire_phaser_klingon(state, surface)
        else:
            fire_klingon_torpedo(state)

    # 5. Random impulse
    if random_next(state.rng_state) % PROB_IMPULSE == 0:
        ship.flags |= THRUST_BIT
    else:
        ship.flags &= ~THRUST_BIT

    # 6. Random hyperspace
    if random_next(state.rng_state) % PROB_HYPER == 0:
        _activate_hyperspace(state, KLN_OBJ)
