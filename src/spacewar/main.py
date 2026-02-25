"""main.py — game loop and top-level orchestration.

Mirrors MAIN.ASM.

The game loop runs at TARGET_FPS=73 Hz (matching the original DOS interrupt rate).

Loop order (mirrors Play_Interrupt + main loop in MAIN.ASM):
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
  11. Flip display

Entry point: main()
"""

from __future__ import annotations

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
)
from .init import new_game_state, reset_game_objects, GameState
from .stars import seed_random, generate_stars
from .keys import KeyState, update_key_state, process_enterprise_keys, process_klingon_keys, process_function_keys
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

def handle_death(dead_idx: int, state: GameState) -> None:
    """Start ship death explosion — score, sound, and begin animation.

    Does NOT reset objects or change mode; the game loop continues running so
    the explosion plays out. The loop detects EFLG_INACTIVE and then resets.

    Mirrors the death-handling section of MAIN.ASM.
    """
    if dead_idx == ENT_OBJ:
        state.klingon_score += 1
    else:
        state.enterprise_score += 1

    state.sound_flag |= EXPLOSION_SOUND

    ship = state.objects[dead_idx]
    ship.eflg = EFLG_EXPLODING
    ship.exps = SHIP_EXPLOSION_TICKS
    # Stop ship movement so the explosion stays centred
    ship.vx = ship.vy = 0
    ship.vx_frac = ship.vy_frac = 0


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Initialise pygame and run the game loop."""
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption('SPACEWAR  v1.72  (1985 B. SEILER)')
    clock = pygame.time.Clock()

    # Initialise game state
    state = new_game_state()
    seed_random(state.rng_state)
    state.star_positions = generate_stars(state.rng_state)
    bg = create_background(state.star_positions)

    # Sound
    sounds = init_sound()

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

        # --- Attract mode ---
        if state.game_mode == MODE_ATTRACT:
            pending_death = -1
            mode = run_attract_tick(state, attract, screen, key_state)
            # Function keys active during attract
            process_function_keys(state, key_state)
            draw_attract_screen(screen, state, attract)
            draw_function_keys(screen, state)
            pygame.display.flip()
            continue

        # --- Play mode ---

        # If a death explosion finished, now reset and switch to attract
        if pending_death >= 0:
            ship = state.objects[pending_death]
            if ship.eflg == EFLG_INACTIVE:
                reset_game_objects(state)
                state.game_mode = MODE_ATTRACT
                pending_death = -1
                continue

        # Phaser erase must happen at tick PHASER_ERASE (before new draw)
        ent = state.objects[ENT_OBJ]
        kln = state.objects[KLN_OBJ]

        if ent.phaser_state == PHASER_ERASE:
            erase_phaser_enterprise(state, screen)
            ent.phaser_state -= 1   # advance past PHASER_ERASE; physics skips it
        if kln.phaser_state == PHASER_ERASE:
            erase_phaser_klingon(state, screen)
            kln.phaser_state -= 1

        # Key / AI processing (pass screen so phasers can be drawn)
        # Skip input during death explosion so the ship can't be controlled
        if pending_death < 0:
            process_enterprise_keys(state, key_state, screen)
            process_klingon_keys(state, key_state, screen)
        process_function_keys(state, key_state)

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
        draw_game_frame(screen, bg, state)
        # Restore phaser beams wiped by the background blit
        redraw_phaser_enterprise(state, screen)
        redraw_phaser_klingon(state, screen)
        draw_energy_bars(screen, state)
        draw_function_keys(screen, state)

        pygame.display.flip()

    pygame.quit()
    sys.exit(0)


if __name__ == '__main__':
    main()
