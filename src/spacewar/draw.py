"""draw.py — all rendering logic.

Mirrors DRAW.ASM + SPSET.ASM.

Coordinate system
-----------------
All game logic uses *virtual* coordinates: x ∈ [0, VIRTUAL_W), y ∈ [0, VIRTUAL_H).
The screen is (SCREEN_W × SCREEN_H) = 640 × 480.
Mapping: screen_x = virtual_x, screen_y = virtual_y * Y_SCALE (Y_SCALE=2).

Surface strategy
----------------
background_surface — 640×480, stars painted once at game start; never modified
Each frame: clear screen → blit background → draw all objects → HUD → flip

Public API
----------
virt_to_screen(x, y) -> tuple[int, int]
put_pixel(surface, x, y, color)
draw_sprite(surface, bitmap, cx, cy, color)
draw_starfield(surface, stars)
draw_game_frame(screen, bg, state)
draw_energy_bars(surface, state)
draw_function_keys(surface, state)
create_background(stars) -> pygame.Surface
"""

from __future__ import annotations

import pygame

from .constants import (
    VIRTUAL_W, VIRTUAL_H, SCREEN_W, SCREEN_H, Y_SCALE,
    ENT_OBJ, KLN_OBJ,
    ENT_TORP_START, ENT_TORP_END, KLN_TORP_START, KLN_TORP_END,
    EFLG_ACTIVE, EFLG_EXPLODING, EFLG_INACTIVE,
    CLOAK_BIT, REDRAW_BIT,
    PLANET_BIT,
    PLANET_X, PLANET_Y,
    STARTING_SHIELDS, STARTING_ENERGY,
    PHASER_ERASE,
    MODE_ATTRACT, MODE_PLAY,
    EXPLOSION_FRAMES,
    AUTO_ENT_BIT, AUTO_KLN_BIT,
    GRAVITY_BIT, PLANET_BIT,
    LOW_SHIELD_LIMIT,
)
from .init import GameState
from .pictures import (
    get_enterprise_sprite, get_klingon_sprite,
    get_explosion_frame, get_planet_frame,
)

# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------
_BLACK = (0, 0, 0)
_WHITE = (255, 255, 255)
_DIM = (100, 100, 100)       # dim white for stars
_GREEN = (0, 220, 0)
_YELLOW = (220, 220, 0)
_RED = (220, 0, 0)
_CYAN = (0, 220, 220)

# Ship colours
_ENT_COLOR = _WHITE
_KLN_COLOR = _WHITE
_TORP_COLOR = _WHITE
_PLANET_COLOR = _WHITE
_STAR_COLOR = _DIM


# ---------------------------------------------------------------------------
# Coordinate helpers
# ---------------------------------------------------------------------------

def virt_to_screen(x: int, y: int) -> tuple[int, int]:
    """Convert virtual (x,y) to screen pixel coordinates."""
    return x, y * Y_SCALE


def put_pixel(surface: pygame.Surface, vx: int, vy: int, color: tuple) -> None:
    """Draw a single virtual pixel as Y_SCALE screen rows."""
    sx, sy = virt_to_screen(vx, vy)
    if 0 <= sx < SCREEN_W and 0 <= sy < SCREEN_H:
        surface.set_at((sx, sy), color)
        if Y_SCALE > 1 and sy + 1 < SCREEN_H:
            surface.set_at((sx, sy + 1), color)


# ---------------------------------------------------------------------------
# Sprite renderer
# ---------------------------------------------------------------------------

def draw_sprite(
    surface: pygame.Surface,
    bitmap: list[int],
    cx: int,
    cy: int,
    color: tuple,
) -> None:
    """Draw an 8×8 bitmask sprite centred on virtual (cx, cy).

    Each bit is rendered as 2 horizontal virtual pixels so the sprite occupies
    16×8 virtual → 16×16 screen pixels (square, not a tall sliver).
    Each row is also drawn as Y_SCALE screen rows via put_pixel.
    Bit 7 of each row byte = leftmost pixel.
    """
    for row_idx, row_bits in enumerate(bitmap):
        vy = cy - 4 + row_idx
        if row_bits == 0:
            continue
        for bit in range(8):
            if row_bits & (1 << (7 - bit)):
                vx = cx - 8 + bit * 2   # 2× horizontal scale; centred at cx
                put_pixel(surface, vx,     vy, color)
                put_pixel(surface, vx + 1, vy, color)


def erase_sprite(
    surface: pygame.Surface,
    bitmap: list[int],
    cx: int,
    cy: int,
) -> None:
    """Erase an 8×8 sprite by drawing black over it."""
    draw_sprite(surface, bitmap, cx, cy, _BLACK)


# ---------------------------------------------------------------------------
# Starfield
# ---------------------------------------------------------------------------

def draw_starfield(surface: pygame.Surface, stars: list[tuple[int, int]]) -> None:
    """Draw all 512 stars as single pixels.  Called once to build background."""
    for (vx, vy) in stars:
        put_pixel(surface, vx, vy, _STAR_COLOR)


def create_background(stars: list[tuple[int, int]]) -> pygame.Surface:
    """Create a static background surface with all stars painted."""
    bg = pygame.Surface((SCREEN_W, SCREEN_H))
    bg.fill(_BLACK)
    draw_starfield(bg, stars)
    return bg


# ---------------------------------------------------------------------------
# Planet
# ---------------------------------------------------------------------------

def draw_planet(surface: pygame.Surface, state: GameState, attract: bool = False) -> None:
    """Draw animated planet at centre (game) or top-right (attract)."""
    if attract:
        from .constants import ATTRACT_PLANET_X, ATTRACT_PLANET_Y
        px = ATTRACT_PLANET_X - 8
        py = ATTRACT_PLANET_Y
    else:
        px = PLANET_X - 8
        py = PLANET_Y - 8

    frame = get_planet_frame(state.planet_state)
    for row_idx, row in enumerate(frame):
        for bit in range(16):
            if row & (1 << (15 - bit)):
                vx = px + bit
                vy = py + row_idx
                put_pixel(surface, vx, vy, _PLANET_COLOR)


# ---------------------------------------------------------------------------
# Ship and torpedo rendering
# ---------------------------------------------------------------------------

def draw_enterprise(surface: pygame.Surface, state: GameState) -> None:
    """Draw Enterprise ship."""
    ship = state.objects[ENT_OBJ]
    if ship.eflg == EFLG_INACTIVE:
        return
    if ship.eflg == EFLG_EXPLODING:
        _draw_explosion(surface, ship)
        return
    if ship.flags & CLOAK_BIT:
        return   # cloaked — invisible
    bitmap = get_enterprise_sprite(ship.angle)
    draw_sprite(surface, bitmap, ship.x, ship.y, _ENT_COLOR)
    ship.x_drawn = ship.x
    ship.y_drawn = ship.y
    ship.angle_drawn = ship.angle
    ship.uflg &= ~REDRAW_BIT


def draw_klingon(surface: pygame.Surface, state: GameState) -> None:
    """Draw Klingon ship."""
    ship = state.objects[KLN_OBJ]
    if ship.eflg == EFLG_INACTIVE:
        return
    if ship.eflg == EFLG_EXPLODING:
        _draw_explosion(surface, ship)
        return
    if ship.flags & CLOAK_BIT:
        return
    bitmap = get_klingon_sprite(ship.angle)
    draw_sprite(surface, bitmap, ship.x, ship.y, _KLN_COLOR)
    ship.x_drawn = ship.x
    ship.y_drawn = ship.y
    ship.angle_drawn = ship.angle
    ship.uflg &= ~REDRAW_BIT


def draw_torpedoes(surface: pygame.Surface, state: GameState) -> None:
    """Draw all active torpedoes as single pixels."""
    for i in list(range(ENT_TORP_START, ENT_TORP_END)) + list(range(KLN_TORP_START, KLN_TORP_END)):
        obj = state.objects[i]
        if obj.eflg == EFLG_ACTIVE:
            put_pixel(surface, obj.x, obj.y, _TORP_COLOR)
        elif obj.eflg == EFLG_EXPLODING:
            _draw_explosion(surface, obj)


def _draw_explosion(surface: pygame.Surface, obj) -> None:
    """Draw explosion animation frame for an object."""
    frame_idx = 7 - max(0, obj.exps - 1)   # counts down: exps=8→frame0, exps=1→frame7
    frame_idx = max(0, min(7, frame_idx))
    bitmap = get_explosion_frame(frame_idx)
    draw_sprite(surface, bitmap, obj.x, obj.y, _WHITE)


# ---------------------------------------------------------------------------
# Hyperspace particles
# ---------------------------------------------------------------------------

def draw_hyper_particles(surface: pygame.Surface, state: GameState) -> None:
    """Draw scatter particles for both ships' hyperspace animations."""
    for flag_attr, particle_start in (('hyper_ent_flag', 0), ('hyper_kln_flag', 32)):
        if getattr(state, flag_attr) == 0:
            continue
        for p in state.hyper_particles[particle_start:particle_start + 32]:
            if p.active:
                vx = int(p.x)
                vy = int(p.y)
                put_pixel(surface, vx, vy, _WHITE)


# ---------------------------------------------------------------------------
# HUD — energy bars
# ---------------------------------------------------------------------------

def draw_energy_bars(surface: pygame.Surface, state: GameState) -> None:
    """Draw S and E energy bars for both ships at the bottom of the screen.

    Mirrors the HUD rendering section of DRAW.ASM.
    """
    bar_y = SCREEN_H - 24   # base y position (screen coords)
    bar_h = 8               # bar height in screen pixels

    def _bar(x_start: int, width: int, value: int, max_val: int, color: tuple) -> None:
        filled = int(width * max(0, value) / max_val)
        rect = pygame.Rect(x_start, bar_y, filled, bar_h)
        pygame.draw.rect(surface, color, rect)
        # Outline
        pygame.draw.rect(surface, _DIM, (x_start, bar_y, width, bar_h), 1)

    ent = state.objects[ENT_OBJ]
    kln = state.objects[KLN_OBJ]

    margin = 10
    bar_w = 120

    # Enterprise — left side
    s_color = _RED if ent.shields < LOW_SHIELD_LIMIT else _GREEN
    _bar(margin, bar_w, ent.shields, STARTING_SHIELDS, s_color)
    _bar(margin, bar_w, ent.energy, STARTING_ENERGY, _CYAN)   # overlay energy

    # Separate S/E bars
    _bar(margin,          bar_w, ent.shields, STARTING_SHIELDS, s_color)
    _bar(margin + bar_w + 4, bar_w, ent.energy, STARTING_ENERGY, _CYAN)

    # Klingon — right side
    s_color_k = _RED if kln.shields < LOW_SHIELD_LIMIT else _YELLOW
    right_margin = SCREEN_W - margin - bar_w
    _bar(right_margin,          bar_w, kln.shields, STARTING_SHIELDS, s_color_k)
    _bar(right_margin - bar_w - 4, bar_w, kln.energy, STARTING_ENERGY, _CYAN)

    # Labels
    font = pygame.font.SysFont('monospace', 12)
    def _lbl(text, x, color):
        surf = font.render(text, True, color)
        surface.blit(surf, (x, bar_y - 14))

    _lbl('S', margin, _GREEN)
    _lbl('E', margin + bar_w + 4, _CYAN)
    _lbl('S', right_margin + bar_w - 8, _YELLOW)
    _lbl('E', right_margin - bar_w - 4, _CYAN)

    # Scores
    score_font = pygame.font.SysFont('monospace', 14)
    ent_surf = score_font.render(f'ENT: {state.enterprise_score}', True, _GREEN)
    kln_surf = score_font.render(f'KLN: {state.klingon_score}', True, _YELLOW)
    surface.blit(ent_surf, (margin, SCREEN_H - 14))
    surface.blit(kln_surf, (SCREEN_W - margin - kln_surf.get_width(), SCREEN_H - 14))


# ---------------------------------------------------------------------------
# HUD — function key footer
# ---------------------------------------------------------------------------

_FKEY_LABELS = [
    ('F1', 'ATTRACT'), ('F2', 'PLAY'), ('F3', 'ENT-AI'), ('F4', 'KLN-AI'),
    ('F5', 'PLANET'),  ('F6', 'GRAV'),  ('F7', 'PAUSE'), ('F8', 'SOUND'),
]


def draw_function_keys(surface: pygame.Surface, state: GameState) -> None:
    """Draw F1–F8 footer bar, highlighting active toggles.

    Mirrors the F-key footer in DRAW.ASM.
    """
    font = pygame.font.SysFont('monospace', 11)
    footer_y = SCREEN_H - 48
    cell_w = SCREEN_W // 8

    toggle_state = [
        False,                                      # F1 (attract) — always off here
        state.game_mode == MODE_PLAY,               # F2
        bool(state.auto_flag & AUTO_ENT_BIT),       # F3
        bool(state.auto_flag & AUTO_KLN_BIT),       # F4
        bool(state.planet_enable & PLANET_BIT),     # F5
        bool(state.planet_enable & GRAVITY_BIT),    # F6
        state.pause_enable,                         # F7
        state.sound_enable,                         # F8
    ]

    for i, ((key, label), active) in enumerate(zip(_FKEY_LABELS, toggle_state)):
        x = i * cell_w
        bg_color = _DIM if not active else _GREEN
        pygame.draw.rect(surface, bg_color, (x, footer_y, cell_w - 1, 12))
        key_surf = font.render(f'{key} {label}', True, _BLACK if active else _WHITE)
        surface.blit(key_surf, (x + 2, footer_y + 1))


# ---------------------------------------------------------------------------
# Master frame draw
# ---------------------------------------------------------------------------

def draw_game_frame(
    screen: pygame.Surface,
    bg: pygame.Surface,
    state: GameState,
) -> None:
    """Render one complete game frame.

    Order:
      1. Blit star background
      2. Planet (if enabled)
      3. Ships and torpedoes
      4. Hyperspace particles
      (Phaser beam is drawn/erased by phaser.py via main.py)
    """
    screen.blit(bg, (0, 0))

    if state.planet_enable & PLANET_BIT:
        draw_planet(screen, state, attract=False)

    draw_enterprise(screen, state)
    draw_klingon(screen, state)
    draw_torpedoes(screen, state)
    draw_hyper_particles(screen, state)
