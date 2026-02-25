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
    """Handle a ship death — increment score, reset objects, return to attract.

    Mirrors the death-handling section of MAIN.ASM.
    """
    if dead_idx == ENT_OBJ:
        state.klingon_score += 1
    else:
        state.enterprise_score += 1

    # Trigger explosion sound
    state.sound_flag |= EXPLOSION_SOUND

    # Mark the dead ship as exploding (let the explosion animation play)
    ship = state.objects[dead_idx]
    ship.eflg = EFLG_EXPLODING
    ship.exps = 8

    # After a short delay, transition to attract mode (simplified: immediate)
    # A more faithful implementation would wait for the explosion to finish.
    # Reset objects and switch to attract mode.
    reset_game_objects(state)
    state.game_mode = MODE_ATTRACT


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
            mode = run_attract_tick(state, attract, screen, key_state)
            # Function keys active during attract
            process_function_keys(state, key_state)
            draw_attract_screen(screen, state, attract)
            draw_function_keys(screen, state)
            pygame.display.flip()
            continue

        # --- Play mode ---

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
        process_enterprise_keys(state, key_state, screen)
        process_klingon_keys(state, key_state, screen)
        process_function_keys(state, key_state)

        # Physics tick
        run_physics_tick(state)

        # Collision detection
        check_all_collisions(state)

        # Death check
        dead = check_death(state)
        if dead >= 0:
            handle_death(dead, state)
            # Render one more frame to show the explosion
            draw_game_frame(screen, bg, state)
            draw_energy_bars(screen, state)
            draw_function_keys(screen, state)
            pygame.display.flip()
            pygame.time.wait(800)
            continue

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
