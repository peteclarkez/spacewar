"""physics.py — per-tick game physics (the Play_Interrupt handler).

Mirrors PLAYINT.ASM.

run_physics_tick(state) is called once per frame at TARGET_FPS=73 Hz.
All timing is gated off the 8-bit BLINK counter (incremented each tick).

Key subsystems handled here:
  - Angle update (ship rotation)
  - Thrust (direction × ACCEL_SCALE) → fractional velocity
  - Cloak energy drain
  - Position integration (32-bit fixed-point with carry)
  - Screen wrapping (WRAP_FACTOR border)
  - Bowl gravity (delegated to gravity.py)
  - Energy recharge (every DILITHIUM_TIME=256 ticks)
  - Torpedo energy drain (every PHOTON_TIME=16 ticks)
  - Phaser state-machine countdown
  - Shield warning sound gating
  - Planet animation

Public API
----------
run_physics_tick(state)       — master per-tick update
update_position(obj)          — integrate one object's velocity into position
"""

from .constants import (
    ENT_OBJ, KLN_OBJ, NUM_OBJECTS,
    ENT_TORP_START, ENT_TORP_END,
    KLN_TORP_START, KLN_TORP_END,
    EFLG_ACTIVE, EFLG_INACTIVE, EFLG_EXPLODING,
    THRUST_BIT, CLOAK_BIT, REDRAW_BIT,
    MAX_X_VEL, MAX_Y_VEL,
    ACCEL_SCALE,
    VIRTUAL_W, VIRTUAL_H, WRAP_FACTOR,
    IMPULSE_TIME, CLOAK_TIME, DILITHIUM_TIME, PHOTON_TIME,
    PLANET_TIME, WARNING_TIME,
    PHASER_IDLE, PHASER_ERASE,
    STARTING_ENERGY,
    WARNING_SOUND, LOW_SHIELD_LIMIT,
    HYPER_DURATION,
)
from .trig import cos_lookup, sin_lookup
from .gravity import update_gravity_all
from .init import GameObject, GameState


# ---------------------------------------------------------------------------
# Rotation
# ---------------------------------------------------------------------------

def _update_angles(state: GameState) -> None:
    """Apply rotation delta to both ships.  Mirrors angle update in PLAYINT.ASM."""
    for idx in (ENT_OBJ, KLN_OBJ):
        obj = state.objects[idx]
        if obj.eflg == EFLG_ACTIVE:
            obj.angle = (obj.angle + obj.rotate) & 0xFF


# ---------------------------------------------------------------------------
# Thrust
# ---------------------------------------------------------------------------

def _add_accel_to_vel(obj: GameObject, accel_x: int, accel_y: int) -> None:
    """Add signed acceleration to fractional velocity with carry propagation.

    Mirrors 'add XVELL[si], ax / adc XVEL[si], 0' in PLAYINT.ASM.
    """
    new_vx_frac = obj.vx_frac + accel_x
    carry_x = new_vx_frac >> 16
    obj.vx_frac = new_vx_frac & 0xFFFF
    obj.vx += carry_x

    new_vy_frac = obj.vy_frac + accel_y
    carry_y = new_vy_frac >> 16
    obj.vy_frac = new_vy_frac & 0xFFFF
    obj.vy += carry_y


def _clamp_velocity(obj: GameObject) -> None:
    """Clamp velocity to ±MAX_X/Y_VEL.  Clears fractional part on clamp."""
    if obj.vx > MAX_X_VEL:
        obj.vx = MAX_X_VEL
        obj.vx_frac = 0
    elif obj.vx < -MAX_X_VEL:
        obj.vx = -MAX_X_VEL
        obj.vx_frac = 0
    if obj.vy > MAX_Y_VEL:
        obj.vy = MAX_Y_VEL
        obj.vy_frac = 0
    elif obj.vy < -MAX_Y_VEL:
        obj.vy = -MAX_Y_VEL
        obj.vy_frac = 0


def apply_thrust(obj: GameObject, blink: int) -> None:
    """Apply thrust impulse in current facing direction.

    Mirrors impulse handling in PLAYINT.ASM:
    - Acceleration = cos/sin(angle) >> ACCEL_SCALE (divide by 8)
    - Energy drains 1 unit every IMPULSE_TIME=32 ticks
    """
    if not (obj.flags & THRUST_BIT):
        return

    # Acceleration in x and y
    accel_x = cos_lookup(obj.angle) >> ACCEL_SCALE
    accel_y = sin_lookup(obj.angle) >> ACCEL_SCALE

    _add_accel_to_vel(obj, accel_x, accel_y)
    _clamp_velocity(obj)

    # Drain energy every IMPULSE_TIME ticks
    if (blink & (IMPULSE_TIME - 1)) == 0:
        if obj.energy > 0:
            obj.energy -= 1


def apply_cloak_drain(obj: GameObject, blink: int) -> None:
    """Drain energy while cloaking.  Mirrors cloak logic in PLAYINT.ASM."""
    if not (obj.flags & CLOAK_BIT):
        return
    if (blink & (CLOAK_TIME - 1)) == 0:
        if obj.energy > 0:
            obj.energy -= 1
        else:
            obj.flags &= ~CLOAK_BIT    # auto-disable cloak when out of energy


# ---------------------------------------------------------------------------
# Position integration (32-bit fixed-point with screen wrap)
# ---------------------------------------------------------------------------

def update_position(obj: GameObject) -> None:
    """Integrate velocity into position for one object, applying screen wrap.

    Mirrors the position update loop in PLAYINT.ASM.
    Uses 32-bit fixed-point arithmetic: (x:x_frac) += (vx:vx_frac)
    Screen wraps at WRAP_FACTOR border.
    """
    if obj.eflg == EFLG_INACTIVE:
        return

    # X axis: add velocity (integer + fractional carry)
    total_x_frac = obj.x_frac + obj.vx_frac
    carry_x = total_x_frac >> 16
    obj.x_frac = total_x_frac & 0xFFFF
    new_x = obj.x + obj.vx + carry_x

    # Y axis
    total_y_frac = obj.y_frac + obj.vy_frac
    carry_y = total_y_frac >> 16
    obj.y_frac = total_y_frac & 0xFFFF
    new_y = obj.y + obj.vy + carry_y

    # Screen wrap — objects re-enter from the opposite edge
    if new_x >= VIRTUAL_W - WRAP_FACTOR:
        new_x = WRAP_FACTOR
    elif new_x < WRAP_FACTOR:
        new_x = VIRTUAL_W - WRAP_FACTOR - 1

    if new_y >= VIRTUAL_H - WRAP_FACTOR:
        new_y = WRAP_FACTOR
    elif new_y < WRAP_FACTOR:
        new_y = VIRTUAL_H - WRAP_FACTOR - 1

    if new_x != obj.x or new_y != obj.y:
        obj.uflg |= REDRAW_BIT

    obj.x = new_x
    obj.y = new_y


# ---------------------------------------------------------------------------
# Energy recharge
# ---------------------------------------------------------------------------

def _tick_energy_recharge(state: GameState) -> None:
    """Recharge both ships by +1 energy every DILITHIUM_TIME ticks.

    DILITHIUM_TIME = 256 → fires when blink == 0 (wraps around).
    Energy capped at STARTING_ENERGY = 127.
    """
    if state.blink != 0:
        return
    for idx in (ENT_OBJ, KLN_OBJ):
        obj = state.objects[idx]
        if obj.eflg == EFLG_ACTIVE and 0 < obj.energy < STARTING_ENERGY:
            obj.energy += 1


# ---------------------------------------------------------------------------
# Torpedo energy drain
# ---------------------------------------------------------------------------

def _tick_torpedo_energy(state: GameState) -> None:
    """Drain 1 energy from each active torpedo every PHOTON_TIME=16 ticks.

    When a torpedo's energy reaches 0, it explodes.
    Mirrors PLAYINT.ASM torpedo timer.
    """
    if (state.blink & (PHOTON_TIME - 1)) != 0:
        return
    for i in list(range(ENT_TORP_START, ENT_TORP_END)) + list(range(KLN_TORP_START, KLN_TORP_END)):
        obj = state.objects[i]
        if obj.eflg == EFLG_ACTIVE:
            obj.energy -= 1
            if obj.energy <= 0:
                obj.eflg = EFLG_EXPLODING
                obj.exps = 8


# ---------------------------------------------------------------------------
# Phaser state machine
# ---------------------------------------------------------------------------

def _tick_phaser_states(state: GameState) -> None:
    """Decrement phaser countdown for both ships each tick.

    State machine:
      PHASER_IDLE (255) → stays at 255
      PHASER_ERASE (20) → skip (main loop handles erase this tick)
      all other values → decrement; when reaching 0 → reset to PHASER_IDLE

    Mirrors the phaser timer in PLAYINT.ASM.
    """
    for idx in (ENT_OBJ, KLN_OBJ):
        obj = state.objects[idx]
        ps = obj.phaser_state
        if ps == PHASER_IDLE:
            continue
        if ps == PHASER_ERASE:
            continue   # main.py handles erase this tick; don't decrement
        ps -= 1
        if ps <= 0:
            obj.phaser_state = PHASER_IDLE
        else:
            obj.phaser_state = ps


# ---------------------------------------------------------------------------
# Shield warning
# ---------------------------------------------------------------------------

def _tick_shield_warning(state: GameState) -> None:
    """Toggle warning sound when shields are low.

    Fires every WARNING_TIME=32 ticks.
    Mirrors the shield warning logic in PLAYINT.ASM.
    """
    if (state.blink & (WARNING_TIME - 1)) != 0:
        return
    warning_needed = False
    for idx in (ENT_OBJ, KLN_OBJ):
        obj = state.objects[idx]
        if obj.eflg == EFLG_ACTIVE and obj.shields < LOW_SHIELD_LIMIT:
            warning_needed = True
    if warning_needed:
        state.sound_flag |= WARNING_SOUND
    else:
        state.sound_flag &= ~WARNING_SOUND


# ---------------------------------------------------------------------------
# Explosion animation
# ---------------------------------------------------------------------------

def _tick_explosions(state: GameState) -> None:
    """Advance explosion animation counters.

    When exps reaches 0 the object becomes EFLG_INACTIVE.
    """
    for obj in state.objects:
        if obj.eflg == EFLG_EXPLODING:
            if obj.exps > 0:
                obj.exps -= 1
            if obj.exps == 0:
                obj.eflg = EFLG_INACTIVE


# ---------------------------------------------------------------------------
# Planet animation
# ---------------------------------------------------------------------------

def _tick_planet_animation(state: GameState) -> None:
    """Advance planet animation frame every PLANET_TIME=16 ticks."""
    if (state.blink & (PLANET_TIME - 1)) != 0:
        return
    state.planet_state = (state.planet_state + 1) & 0x0F


# ---------------------------------------------------------------------------
# Hyperspace animation
# ---------------------------------------------------------------------------

def _tick_hyperspace(state: GameState) -> None:
    """Advance hyperspace particle animation for both ships."""
    import random as _random

    for flag_attr, particle_start in (('hyper_ent_flag', 0), ('hyper_kln_flag', 32)):
        flag = getattr(state, flag_attr)
        if flag == 0:
            continue

        # Advance particles
        for p in state.hyper_particles[particle_start:particle_start + 32]:
            if not p.active:
                continue
            p.x += p.vx
            p.y += p.vy

        flag += 1
        if flag > HYPER_DURATION:
            # Animation over — teleport the ship
            flag = 0
            ship_idx = ENT_OBJ if particle_start == 0 else 8  # KLN_OBJ
            ship = state.objects[ship_idx]
            # Arrive at random position with zero velocity
            ship.x = _random.randint(WRAP_FACTOR + 16, VIRTUAL_W - WRAP_FACTOR - 16)
            ship.y = _random.randint(WRAP_FACTOR + 16, VIRTUAL_H - WRAP_FACTOR - 16)
            ship.vx = ship.vy = 0
            ship.vx_frac = ship.vy_frac = 0
            ship.eflg = EFLG_ACTIVE
            for p in state.hyper_particles[particle_start:particle_start + 32]:
                p.active = False

        setattr(state, flag_attr, flag)


# ---------------------------------------------------------------------------
# Torp debounce release
# ---------------------------------------------------------------------------

def _release_debounce(state: GameState) -> None:
    """Clear fire debounce flags each tick so held keys don't re-fire immediately.

    The ASM clears TORP_FIRE_BIT when the key is released; here we simply
    clear it each tick (key processing in keys.py sets it on press).
    NOTE: The debounce is set on fire and cleared here; keys.py must re-set
    it before this runs if the key is still held.
    """
    # Debounce is actually cleared in keys.py when the key is released.
    # This function is a placeholder for future ASM-accurate debounce.
    pass


# ---------------------------------------------------------------------------
# Master physics tick
# ---------------------------------------------------------------------------

def run_physics_tick(state: GameState) -> None:
    """Run one full physics tick — called once per frame at TARGET_FPS.

    Mirrors Play_Interrupt in PLAYINT.ASM (the timer-driven ISR).
    """
    # 1. Advance blink counter (8-bit wrap)
    state.blink = (state.blink + 1) & 0xFF

    # 2. Paused — skip all updates
    if state.pause_enable:
        return

    # 3. Ship angle and thrust
    _update_angles(state)
    for idx in (ENT_OBJ, KLN_OBJ):
        obj = state.objects[idx]
        if obj.eflg == EFLG_ACTIVE:
            apply_thrust(obj, state.blink)
            apply_cloak_drain(obj, state.blink)

    # 4. Integrate positions for ALL active/exploding objects
    for obj in state.objects:
        update_position(obj)

    # 5. Bowl gravity (if enabled)
    update_gravity_all(state)

    # 6. Energy recharge
    _tick_energy_recharge(state)

    # 7. Torpedo lifetime drain
    _tick_torpedo_energy(state)

    # 8. Phaser state machine
    _tick_phaser_states(state)

    # 9. Shield warning sound
    _tick_shield_warning(state)

    # 10. Explosion advancement
    _tick_explosions(state)

    # 11. Planet animation
    _tick_planet_animation(state)

    # 12. Hyperspace animation
    _tick_hyperspace(state)

    # Import here to avoid circular — sound is handled by main after physics
    # (sound.py ticked by main.py)
