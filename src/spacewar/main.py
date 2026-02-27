"""main.py — game loop and top-level orchestration.

The game loop runs at TARGET_FPS=73 Hz (matching the original DOS interrupt rate).

Loop order:
  1. Clock tick
  2. Process pygame events (quit, etc.)
  3. Update key state
  4. Phaser erase (at PHASER_ERASE tick — must happen before redraw)
  5. Key / AI processing (with surface for phaser drawing)
  6. Physics tick
  7. Collision detection
  8. Death check → handle death
  9. Draw game frame
  10. HUD (energy bars, function keys)
  11. Scale game_surface → screen and flip display

Entry point: main()
"""

from __future__ import annotations

import argparse
import sys

import pygame

from .constants import (
    SCREEN_W, SCREEN_H, TARGET_FPS,
    ENT_OBJ, KLN_OBJ,
    EFLG_ACTIVE, EFLG_EXPLODING, EFLG_INACTIVE,
    PHASER_ERASE, PHASER_IDLE,
    EXPLOSION_SOUND,
    MODE_ATTRACT, MODE_PLAY,
    HYPER_DURATION,
    SHIP_EXPLOSION_TICKS,
    HYPER_PARTICLES, HYPER_SOUND,
)
from .init import new_game_state, reset_game_objects, GameState
from .stars import seed_random, generate_stars
from .keys import KeyState, update_key_state, process_enterprise_keys, process_klingon_keys, process_function_keys
from .joystick import init_joysticks
from .physics import run_physics_tick
from .collision import check_all_collisions, check_death
from .phaser import (
    erase_phaser_enterprise, erase_phaser_klingon,
    redraw_phaser_enterprise, redraw_phaser_klingon,
)
from .sound import init_sound, tick_sound
from .draw import draw_game_frame, draw_energy_bars, draw_function_keys, create_background
from .attract import AttractState, run_attract_tick, draw_attract_screen


# ---------------------------------------------------------------------------
# Death handling
# ---------------------------------------------------------------------------

def _launch_explosion_particles(state: GameState, ship_idx: int) -> None:
    """Launch radial scatter particles for a ship death explosion.

    Reuses the hyperspace particle infrastructure (hyper_particles slots and
    hyper_*_flag).  Because ship.exps > 0 during the animation, _tick_hyperspace
    can distinguish a death explosion from a real jump and skips the contraction
    phase and teleport.
    """
    import math as _math
    import random as _random

    ship = state.objects[ship_idx]
    p_start = 0 if ship_idx == ENT_OBJ else 32

    # More particles spread over a wider speed range than hyperspace for drama
    for i in range(HYPER_PARTICLES):
        p = state.hyper_particles[p_start + i]
        a = (i / HYPER_PARTICLES) * 2 * _math.pi
        speed = _random.uniform(0.15, 1.8)
        p.x = float(ship.x)
        p.y = float(ship.y)
        p.vx = _math.cos(a) * speed
        p.vy = _math.sin(a) * speed * 0.5   # compressed for virtual Y aspect
        p.active = True

    if ship_idx == ENT_OBJ:
        state.hyper_ent_flag = 1
    else:
        state.hyper_kln_flag = 1


def handle_death(dead_idx: int, state: GameState) -> None:
    """Start ship death explosion — score, sound, particles, begin animation.

    Does NOT reset objects or change mode; the game loop continues running so
    the particle explosion plays out. The loop detects EFLG_INACTIVE and resets.

    """
    if dead_idx == ENT_OBJ:
        state.klingon_score += 1
    else:
        state.enterprise_score += 1

    state.sound_flag |= EXPLOSION_SOUND

    ship = state.objects[dead_idx]
    ship.eflg = EFLG_EXPLODING
    ship.exps = SHIP_EXPLOSION_TICKS
    # Stop ship movement so particles expand symmetrically
    ship.vx = ship.vy = 0
    ship.vx_frac = ship.vy_frac = 0

    # Launch hyperspace-style scatter particles for the explosion visual
    _launch_explosion_particles(state, dead_idx)


# ---------------------------------------------------------------------------
# Display scaling helpers
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    """Parse --scale N and --2x arguments.

    Returns a Namespace with attribute ``scale: int`` (default 1).
    """
    parser = argparse.ArgumentParser(
        description='SpaceWar — Python/Pygame recreation of the classic 1985 DOS space combat game'
    )
    parser.add_argument(
        '--scale', type=int, default=1, metavar='N',
        help='Window size multiplier (1=640×480, 2=1280×960, etc.)',
    )
    parser.add_argument(
        '--2x', dest='two_x', action='store_true', default=False,
        help='Alias for --scale 2',
    )
    parser.add_argument(
        '--altkeys', action='store_true', default=False,
        help='Replace right-player numpad controls with UIO/JKL/M,. layout',
    )
    parser.add_argument(
        '--neon', action='store_true', default=False,
        help='Enable neon colour mode (white-hot core + coloured glow on sprites)',
    )
    args = parser.parse_args()
    if args.two_x:
        args.scale = 2
    if args.scale < 1:
        parser.error('--scale must be >= 1')
    if args.scale == 3:
        args.neon = True   # --scale 3 easter egg
    return args


def _compute_letterbox(win_w: int, win_h: int) -> tuple[int, int, int, int]:
    """Return (dest_x, dest_y, dest_w, dest_h) for scaling 640×480 into the window.

    Maintains the 640:480 aspect ratio.  Black bars fill any remaining area.
    """
    scale = min(win_w / SCREEN_W, win_h / SCREEN_H)
    dest_w = int(SCREEN_W * scale)
    dest_h = int(SCREEN_H * scale)
    dest_x = (win_w - dest_w) // 2
    dest_y = (win_h - dest_h) // 2
    return dest_x, dest_y, dest_w, dest_h


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Initialise pygame and run the game loop."""
    args = _parse_args()

    pygame.init()

    win_w = SCREEN_W * args.scale
    win_h = SCREEN_H * args.scale

    # RESIZABLE lets the user drag-resize; aspect ratio is maintained via
    # letterboxing in the scaling blit at the bottom of the loop.
    screen = pygame.display.set_mode((win_w, win_h), pygame.RESIZABLE)
    pygame.display.set_caption('SPACEWAR  1985')
    clock = pygame.time.Clock()

    # Intermediate 640×480 render target.  ALL rendering functions write here.
    # This surface is never resized; the scaling blit below handles any window
    # size changes without touching any draw/phaser/attract code.
    game_surface = pygame.Surface((SCREEN_W, SCREEN_H))

    # Pre-allocate a scaled surface; only reallocated when the window changes size.
    _, _, dw, dh = _compute_letterbox(win_w, win_h)
    scaled_surface = pygame.Surface((dw, dh))

    # Initialise game state
    state = new_game_state()
    state.alt_keys = args.altkeys
    state.neon_mode = args.neon
    seed_random(state.rng_state)
    state.star_positions = generate_stars(state.rng_state)
    bg = create_background(state.star_positions, neon=state.neon_mode)

    # Sound
    sounds = init_sound()

    # Joystick / gamepad (must be after pygame.init())
    joysticks = init_joysticks()

    # Key tracking
    key_state = KeyState()

    # Attract mode state
    attract = AttractState()

    # Track which ship is currently playing its death explosion (-1 = none)
    pending_death: int = -1

    running = True
    while running:
        clock.tick(TARGET_FPS)

        # --- Event processing ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

        # Refresh key state from pygame snapshot
        update_key_state(key_state)
        for joy in joysticks:
            joy.update()

        # --- Attract mode ---
        if state.game_mode == MODE_ATTRACT:
            pending_death = -1
            mode = run_attract_tick(state, attract, game_surface, key_state)
            # Function keys active during attract
            process_function_keys(state, key_state, joysticks)
            draw_attract_screen(game_surface, state, attract)
            draw_function_keys(game_surface, state)

        else:
            # --- Play mode ---

            # If a death explosion finished, reset and switch to attract.
            # Use 'continue'-equivalent: skip the rest of the play block so the
            # scaling blit still runs (shows the last drawn frame for one tick).
            if pending_death >= 0:
                ship = state.objects[pending_death]
                if ship.eflg == EFLG_INACTIVE:
                    reset_game_objects(state)
                    state.game_mode = MODE_ATTRACT
                    pending_death = -1
                    # Fall through to scaling blit with last game_surface content.

            if state.game_mode == MODE_PLAY:
                # Phaser erase must happen at tick PHASER_ERASE (before new draw)
                ent = state.objects[ENT_OBJ]
                kln = state.objects[KLN_OBJ]

                if ent.phaser_state == PHASER_ERASE:
                    erase_phaser_enterprise(state, game_surface)
                    ent.phaser_state -= 1   # advance past PHASER_ERASE; physics skips it
                if kln.phaser_state == PHASER_ERASE:
                    erase_phaser_klingon(state, game_surface)
                    kln.phaser_state -= 1

                # Key / AI processing (pass game_surface so phasers can be drawn)
                # Skip input during death explosion so the ship can't be controlled
                if pending_death < 0:
                    joy0 = joysticks[0] if len(joysticks) > 0 else None
                    joy1 = joysticks[1] if len(joysticks) > 1 else None
                    process_enterprise_keys(state, key_state, game_surface, joy=joy0)
                    process_klingon_keys(state, key_state, game_surface, joy=joy1)
                process_function_keys(state, key_state, joysticks)

                # Physics tick (also decrements exps for all exploding objects)
                run_physics_tick(state)

                # Collision detection (skip while death explosion is playing)
                if pending_death < 0:
                    check_all_collisions(state)

                    # Death check — only trigger once per death
                    dead = check_death(state)
                    if dead >= 0:
                        handle_death(dead, state)
                        pending_death = dead

                # Sound
                tick_sound(state, sounds)

                # Draw
                draw_game_frame(game_surface, bg, state)
                # Restore phaser beams wiped by the background blit
                redraw_phaser_enterprise(state, game_surface)
                redraw_phaser_klingon(state, game_surface)
                draw_energy_bars(game_surface, state)
                draw_function_keys(game_surface, state)

        # --- Scaling blit (runs every frame regardless of mode) ---
        cur_w, cur_h = screen.get_size()
        dest_x, dest_y, dest_w, dest_h = _compute_letterbox(cur_w, cur_h)
        # Reallocate scaled_surface only when the window size changes
        if scaled_surface.get_size() != (dest_w, dest_h):
            scaled_surface = pygame.Surface((dest_w, dest_h))
        # Nearest-neighbour scale into pre-allocated surface (no per-frame alloc)
        pygame.transform.scale(game_surface, (dest_w, dest_h), scaled_surface)
        screen.fill((0, 0, 0))   # black letterbox bars
        screen.blit(scaled_surface, (dest_x, dest_y))
        pygame.display.flip()

    pygame.quit()
    sys.exit(0)


if __name__ == '__main__':
    main()
