"""attract.py — attract mode (title screen sequence).

Mirrors ATTRACT.ASM.

The original cycles through four screens:
  0 — Title + copyright + scores
  1 — Game instructions
  2 — Key layout
  3 — "User supported" message

The SPACEWAR title particle animation from ATTRACT.ASM is stubbed;
a static text placeholder is displayed instead.
# TODO: implement SPACEWAR title particle animation from ATTRACT.ASM

Public API
----------
AttractState — dataclass tracking current screen and timer
run_attract_tick(state, attract, surface, key_state) -> int
draw_attract_screen(surface, state, attract)
"""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from .constants import (
    MODE_PLAY, MODE_ATTRACT,
    ATTRACT_SCREENS, ATTRACT_CYCLE_TIME,
    SCREEN_W, SCREEN_H,
    ATTRACT_PLANET_X, ATTRACT_PLANET_Y,
    AUTO_ENT_BIT, AUTO_KLN_BIT,
    PLANET_BIT, GRAVITY_BIT,
    PLANET_TIME,
)


# Colours
_BLACK = (0, 0, 0)
_WHITE = (255, 255, 255)
_DIM = (128, 128, 128)
_GREEN = (0, 200, 0)
_YELLOW = (200, 200, 0)


@dataclass
class AttractState:
    """Attract mode display state."""
    screen_index: int = 0    # current page (0-3)
    screen_timer: int = 0    # ticks on current page


def run_attract_tick(
    state,          # GameState
    attract: AttractState,
    surface: pygame.Surface,
    key_state,      # KeyState — import avoided to prevent circular
) -> int:
    """Advance attract mode by one tick.

    Returns new game mode (MODE_ATTRACT or MODE_PLAY).
    Mirrors attract-mode sequencing in ATTRACT.ASM.
    """
    attract.screen_timer += 1
    if attract.screen_timer >= ATTRACT_CYCLE_TIME:
        attract.screen_timer = 0
        attract.screen_index = (attract.screen_index + 1) % ATTRACT_SCREENS

    # Advance the blink counter and planet animation (run_physics_tick is not
    # called in attract mode, so we drive timing here instead).
    state.blink = (state.blink + 1) & 0xFF
    if (state.blink & (PLANET_TIME - 1)) == 0:
        state.planet_state = (state.planet_state + 1) & 0x0F

    # F2 starts the game
    if key_state.just_pressed.get(pygame.K_F2):
        from .init import reset_game_objects
        reset_game_objects(state)
        state.pause_enable = False
        state.game_mode = MODE_PLAY
        return MODE_PLAY

    # F3/F4/F5/F6/F8 are active during attract (via process_function_keys in main)
    return MODE_ATTRACT


def draw_attract_screen(
    surface: pygame.Surface,
    state,              # GameState
    attract: AttractState,
) -> None:
    """Render the current attract screen.

    Mirrors the screen-drawing sections of ATTRACT.ASM.
    """
    surface.fill(_BLACK)

    idx = attract.screen_index
    if idx == 0:
        _draw_title_screen(surface, state)
    elif idx == 1:
        _draw_instructions(surface)
    elif idx == 2:
        _draw_key_layout(surface)
    else:
        _draw_user_supported(surface)

    # Planet is shown in top-right corner during attract (ATTRACT.ASM)
    _draw_attract_planet(surface, state)


# ---------------------------------------------------------------------------
# Individual attract screens
# ---------------------------------------------------------------------------

def _font(size: int) -> pygame.font.Font:
    return pygame.font.SysFont('monospace', size)


def _text(surface, text: str, x: int, y: int, color=_WHITE, size: int = 20) -> None:
    font = _font(size)
    surf = font.render(text, True, color)
    surface.blit(surf, (x, y))


def _centred(surface, text: str, y: int, color=_WHITE, size: int = 20) -> None:
    font = _font(size)
    surf = font.render(text, True, color)
    x = (SCREEN_W - surf.get_width()) // 2
    surface.blit(surf, (x, y))


def _draw_title_screen(surface: pygame.Surface, state) -> None:
    """Attract screen 0 — title, copyright, scores.

    # TODO: implement SPACEWAR letter-particle animation from ATTRACT.ASM
    """
    _centred(surface, 'S P A C E W A R', 80, _WHITE, 48)
    _centred(surface, 'COPYRIGHT 1985 B SEILER', 160, _DIM, 16)

    # Scores
    ent_score = getattr(state, 'enterprise_score', 0)
    kln_score = getattr(state, 'klingon_score', 0)
    _text(surface, f'ENTERPRISE: {ent_score}', 80,  240, _GREEN, 20)
    _text(surface, f'KLINGON:    {kln_score}',  80,  270, _YELLOW, 20)

    _centred(surface, 'PRESS F2 TO PLAY', 360, _WHITE, 20)


def _draw_instructions(surface: pygame.Surface) -> None:
    """Attract screen 1 — game instructions."""
    lines = [
        ('SPACEWAR  INSTRUCTIONS', 30, _WHITE, 24),
        ('', 65, _WHITE, 16),
        ('TWO SHIPS BATTLE IN SPACE NEAR A PLANET', 80, _WHITE, 16),
        ('', 100, _WHITE, 16),
        ('SHIELDS (S) ABSORB WEAPON DAMAGE', 110, _DIM, 16),
        ('ENERGY  (E) POWERS ENGINES AND WEAPONS', 130, _DIM, 16),
        ('TRANSFER ENERGY BETWEEN S AND E WITH Z/C', 150, _DIM, 16),
        ('', 170, _WHITE, 16),
        ('PHASERS HIT INSTANTLY — RANGE 96 PX', 180, _WHITE, 16),
        ('TORPEDOES TRAVEL WITH INERTIA & GRAVITY', 200, _WHITE, 16),
        ('HYPERSPACE TELEPORTS TO A RANDOM LOCATION', 220, _WHITE, 16),
        ('', 240, _WHITE, 16),
        ('LAST SHIP STANDING WINS', 260, _WHITE, 20),
        ('', 290, _WHITE, 16),
        ('PRESS F2 TO PLAY', 320, _WHITE, 18),
    ]
    for text, y, color, size in lines:
        if text:
            _centred(surface, text, y, color, size)


def _draw_key_layout(surface: pygame.Surface) -> None:
    """Attract screen 2 — key layout."""
    lines = [
        ('KEY LAYOUT', 20, _WHITE, 24),
        ('', 55, _WHITE, 16),
        ('ENTERPRISE (LEFT)          KLINGON (RIGHT)', 70, _WHITE, 16),
        ('Q = PHASERS                KP7 = PHASERS',   95, _GREEN, 15),
        ('E = TORPEDO                KP9 = TORPEDO',  115, _GREEN, 15),
        ('W = CLOAK                  KP8 = CLOAK',    135, _GREEN, 15),
        ('A/D = ROTATE LEFT/RIGHT    KP4/6 = ROTATE', 155, _GREEN, 15),
        ('S = IMPULSE THRUST         KP5 = IMPULSE',  175, _GREEN, 15),
        ('X = HYPERSPACE             KP2 = HYPERSPACE', 195, _GREEN, 15),
        ('Z = SHIELDS->ENERGY        KP1 = S->E',     215, _GREEN, 15),
        ('C = ENERGY->SHIELDS        KP3 = E->S',     235, _GREEN, 15),
        ('', 255, _WHITE, 16),
        ('FUNCTION KEYS', 265, _WHITE, 18),
        ('F1=ATTRACT  F2=PLAY  F3=ENT-ROBOT  F4=KLN-ROBOT', 285, _DIM, 14),
        ('F5=PLANET   F6=GRAVITY  F7=PAUSE  F8=SOUND',       305, _DIM, 14),
        ('', 325, _WHITE, 16),
        ('PRESS F2 TO PLAY', 345, _WHITE, 18),
    ]
    for text, y, color, size in lines:
        if text:
            _centred(surface, text, y, color, size)


def _draw_user_supported(surface: pygame.Surface) -> None:
    """Attract screen 3 — user-supported message."""
    lines = [
        ('SPACEWAR', 80, _WHITE, 40),
        ('', 130, _WHITE, 16),
        ('THIS PROGRAM IS USER SUPPORTED', 150, _WHITE, 20),
        ('', 175, _WHITE, 16),
        ('IF YOU USE AND ENJOY THIS PROGRAM', 190, _DIM, 18),
        ('PLEASE SEND A CONTRIBUTION TO:', 210, _DIM, 18),
        ('', 230, _WHITE, 16),
        ('BILL SEILER', 245, _WHITE, 20),
        ('(SUPPORT SHAREWARE SOFTWARE)', 275, _DIM, 16),
        ('', 300, _WHITE, 16),
        ('PRESS F2 TO PLAY', 330, _WHITE, 18),
    ]
    for text, y, color, size in lines:
        if text:
            _centred(surface, text, y, color, size)


def _draw_attract_planet(surface: pygame.Surface, state) -> None:
    """Draw animated planet in top-right corner (attract mode position).

    The frame has 8 virtual rows; each virtual row maps to 2 screen rows
    (Y_SCALE=2), producing a 16×16 screen-pixel circle.
    """
    from .pictures import get_planet_frame
    frame = get_planet_frame(state.planet_state)
    px = ATTRACT_PLANET_X - 8
    py = ATTRACT_PLANET_Y
    for row_idx, row in enumerate(frame):
        for bit in range(16):
            if row & (1 << (15 - bit)):
                sx = px + bit
                sy = py * 2 + row_idx * 2   # virtual row → 2 screen rows
                if 0 <= sx < SCREEN_W and 0 <= sy < SCREEN_H:
                    surface.set_at((sx, sy), _WHITE)
                    if sy + 1 < SCREEN_H:
                        surface.set_at((sx, sy + 1), _WHITE)
