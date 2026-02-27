"""
HUD rendering — energy bars, function-key footer, score display.

All drawing targets the 640×480 display surface.
"""

from __future__ import annotations

import pygame

from spacewar.constants import (
    DISPLAY_W, DISPLAY_H,
    BLACK, WHITE,
    STARTING_SHIELDS, STARTING_ENERGY,
    LOW_SHIELD_LIMIT,
    PLAYER_ENT, PLAYER_KLN,
)

# ── Layout constants ──────────────────────────────────────────────────────────
_FOOTER_H    = 20           # Height of the function-key footer strip
_BAR_H       = 8            # Height of each energy bar
_BAR_W_MAX   = 128          # Max width of each bar (represents 127 units)
_BAR_Y_BASE  = DISPLAY_H - _FOOTER_H - _BAR_H * 2 - 4   # Top of P1 bars
_P1_BAR_X    = 4
_P2_BAR_X    = DISPLAY_W - _BAR_W_MAX - 4

_FONT_CACHE: dict[int, pygame.font.Font] = {}


def _font(size: int) -> pygame.font.Font:
    if size not in _FONT_CACHE:
        _FONT_CACHE[size] = pygame.font.SysFont("monospace", size, bold=True)
    return _FONT_CACHE[size]


# ── Energy bars ───────────────────────────────────────────────────────────────

def draw_energy_bars(surface: pygame.Surface, ent_ship, kln_ship, tick: int) -> None:
    """Draw S and E bars for both ships plus shield labels."""

    for player, ship, bar_x in (
        (PLAYER_ENT, ent_ship, _P1_BAR_X),
        (PLAYER_KLN, kln_ship, _P2_BAR_X),
    ):
        # S bar (shields) — top
        s_val = max(0, ship.shields)
        s_w   = int(s_val * _BAR_W_MAX / STARTING_SHIELDS)
        s_y   = _BAR_Y_BASE
        pygame.draw.rect(surface, WHITE, (bar_x, s_y, s_w, _BAR_H))
        pygame.draw.rect(surface, WHITE, (bar_x, s_y, _BAR_W_MAX, _BAR_H), 1)

        # E bar (energy) — below S bar
        e_val = max(0, ship.energy)
        e_w   = int(e_val * _BAR_W_MAX / STARTING_ENERGY)
        e_y   = s_y + _BAR_H + 2
        pygame.draw.rect(surface, WHITE, (bar_x, e_y, e_w, _BAR_H))
        pygame.draw.rect(surface, WHITE, (bar_x, e_y, _BAR_W_MAX, _BAR_H), 1)

        # Labels
        fnt = _font(10)
        # S label blinks when shields critically low
        if not ship.shield_warning or (tick // 16) % 2 == 0:
            s_label = fnt.render("S", True, WHITE)
            surface.blit(s_label, (bar_x + _BAR_W_MAX + 3, s_y))

        e_label = fnt.render("E", True, WHITE)
        surface.blit(e_label, (bar_x + _BAR_W_MAX + 3, e_y))

        # Ship name label
        name = "ENT" if player == PLAYER_ENT else "KLN"
        name_surf = fnt.render(name, True, WHITE)
        lx = bar_x if player == PLAYER_ENT else bar_x - name_surf.get_width() - 2
        surface.blit(name_surf, (lx, _BAR_Y_BASE - 12))


# ── Function-key footer ───────────────────────────────────────────────────────

_F_LABELS = ["F1 Attract", "F2 Play", "F3 Ent Robot", "F4 Kln Robot",
             "F5 Planet", "F6 Gravity", "F7 Pause", "F8 Sound"]

def draw_footer(surface: pygame.Surface, state) -> None:
    """
    Draw the 8 function-key boxes at the bottom of the screen.
    Toggles that are active are shown inverted (white bg, black text).
    state: GameState object with attributes robot_ent, robot_kln,
           planet_on, gravity_on, paused, sound_on.
    """
    fnt = _font(10)
    total_w = DISPLAY_W
    box_w   = total_w // 8
    y0      = DISPLAY_H - _FOOTER_H

    active_flags = [
        False,                  # F1 Attract  — not a toggle
        False,                  # F2 Play     — not a toggle
        state.robot_ent,        # F3
        state.robot_kln,        # F4
        state.planet_on,        # F5
        state.gravity_on,       # F6
        state.paused,           # F7
        state.sound_on,         # F8
    ]

    for i, (label, active) in enumerate(zip(_F_LABELS, active_flags)):
        x0 = i * box_w
        bg = WHITE if active else BLACK
        fg = BLACK if active else WHITE
        pygame.draw.rect(surface, bg,  (x0 + 1, y0 + 1, box_w - 2, _FOOTER_H - 2))
        pygame.draw.rect(surface, WHITE, (x0, y0, box_w, _FOOTER_H), 1)
        txt = fnt.render(label, True, fg)
        surface.blit(txt, (x0 + 2, y0 + (_FOOTER_H - txt.get_height()) // 2))


# ── Score display ─────────────────────────────────────────────────────────────

def draw_scores(surface: pygame.Surface, ent_score: int, kln_score: int) -> None:
    """Display persistent win counts near the energy bars."""
    fnt = _font(12)
    ent_txt = fnt.render(f"ENT {ent_score}", True, WHITE)
    kln_txt = fnt.render(f"KLN {kln_score}", True, WHITE)
    surface.blit(ent_txt, (_P1_BAR_X, _BAR_Y_BASE - 26))
    surface.blit(kln_txt, (DISPLAY_W - kln_txt.get_width() - 4, _BAR_Y_BASE - 26))
