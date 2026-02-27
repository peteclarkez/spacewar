"""draw.py — all rendering logic.

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
    SHIP_EXPLOSION_TICKS,
)
from .init import GameState
from .pictures import (
    get_enterprise_sprite, get_klingon_sprite,
    get_enterprise_torp_sprite, get_klingon_torp_sprite,
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

# Neon glow colours (--neon / --scale 3 mode); core is always _WHITE
_NEON_ENT      = (0,    80, 255)   # electric blue
_NEON_KLN      = (255, 120,   0)   # orange
_NEON_ETOR     = (0,   255, 100)   # green
_NEON_KTOR     = (255,  50,  50)   # red
_NEON_PLT      = (160,  80, 255)   # purple
_NEON_STAR     = (20,   20,  70)   # deep blue
_NEON_PART_ENT = (0,   160, 255)   # blue — Enterprise hyperspace particles
_NEON_PART_KLN = (255,  80,   0)   # orange — Klingon hyperspace particles


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
# Sprites were designed for CGA square pixels.
# We render them at 1:1 screen pixels, centred at screen (vx, vy*Y_SCALE).
# This gives correct proportions regardless of the virtual Y-scale factor.

def _blit_sprite(
    surface: pygame.Surface,
    bitmap: list[int],
    n_bits: int,
    sx0: int,
    sy0: int,
    color: tuple,
) -> None:
    """Core 1:1 sprite blitter.  Draws bitmap rows at direct screen coords.

    Args:
        bitmap : list of row bitmasks (MSB = leftmost pixel)
        n_bits : pixel width of each row (8 for small sprites, 16 for ships)
        sx0    : screen x of leftmost pixel in row 0
        sy0    : screen y of row 0
        color  : RGB tuple
    """
    w = SCREEN_W
    h = SCREEN_H
    for row_idx, row_bits in enumerate(bitmap):
        sy = sy0 + row_idx
        if row_bits == 0 or sy < 0 or sy >= h:
            continue
        for bit in range(n_bits):
            if row_bits & (1 << (n_bits - 1 - bit)):
                sx = sx0 + bit
                if 0 <= sx < w:
                    surface.set_at((sx, sy), color)


def _blit_sprite_neon(
    surface: pygame.Surface,
    bitmap: list[int],
    n_bits: int,
    sx0: int,
    sy0: int,
    glow_color: tuple,
) -> None:
    """Draw a sprite with neon glow effect: coloured halo then white-hot core.

    Pass 1 — each set pixel's 8 neighbours are painted in a dim (50%) version
              of glow_color, creating a soft coloured halo.
    Pass 2 — the exact sprite pixels are overdrawn in pure white, giving a
              bright white-hot core surrounded by the coloured glow.
    """
    w = SCREEN_W
    h = SCREEN_H
    dim = (glow_color[0] // 2, glow_color[1] // 2, glow_color[2] // 2)

    # Pass 1: coloured halo
    for row_idx, row_bits in enumerate(bitmap):
        if row_bits == 0:
            continue
        sy = sy0 + row_idx
        if sy < 0 or sy >= h:
            continue
        for bit in range(n_bits):
            if row_bits & (1 << (n_bits - 1 - bit)):
                sx = sx0 + bit
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if dx == 0 and dy == 0:
                            continue
                        nx = sx + dx
                        ny = sy + dy
                        if 0 <= nx < w and 0 <= ny < h:
                            surface.set_at((nx, ny), dim)

    # Pass 2: white-hot core
    for row_idx, row_bits in enumerate(bitmap):
        if row_bits == 0:
            continue
        sy = sy0 + row_idx
        for bit in range(n_bits):
            if row_bits & (1 << (n_bits - 1 - bit)):
                sx = sx0 + bit
                if 0 <= sx < w and 0 <= sy < h:
                    surface.set_at((sx, sy), _WHITE)


def draw_sprite(
    surface: pygame.Surface,
    bitmap: list[int],
    cx: int,
    cy: int,
    color: tuple,
) -> None:
    """Draw an 8×8 sprite (explosions, torpedoes) centred at virtual (cx, cy).

    Rendered at 1:1 screen pixels; sprite is 8×8 on screen.
    Bit 7 of each row byte = leftmost pixel.
    """
    sx0 = cx - 4
    sy0 = cy * Y_SCALE - 4
    _blit_sprite(surface, bitmap, 8, sx0, sy0, color)


def draw_ship_sprite(
    surface: pygame.Surface,
    bitmap: list[int],
    cx: int,
    cy: int,
    color: tuple,
) -> None:
    """Draw a 16×16 ship sprite centred at virtual (cx, cy).

    Rendered at 1:1 screen pixels; sprite is 16×16 on screen.
    Bit 15 of each row word = leftmost pixel.
    """
    sx0 = cx - 8
    sy0 = cy * Y_SCALE - 8
    _blit_sprite(surface, bitmap, 16, sx0, sy0, color)


# ---------------------------------------------------------------------------
# Starfield
# ---------------------------------------------------------------------------

def draw_starfield(
    surface: pygame.Surface,
    stars: list[tuple[int, int]],
    color: tuple = _STAR_COLOR,
) -> None:
    """Draw all 512 stars as single pixels.  Called once to build background."""
    for (vx, vy) in stars:
        put_pixel(surface, vx, vy, color)


def create_background(
    stars: list[tuple[int, int]],
    neon: bool = False,
) -> pygame.Surface:
    """Create a static background surface with all stars painted."""
    bg = pygame.Surface((SCREEN_W, SCREEN_H))
    bg.fill(_BLACK)
    draw_starfield(bg, stars, color=_NEON_STAR if neon else _STAR_COLOR)
    return bg


# ---------------------------------------------------------------------------
# Planet
# ---------------------------------------------------------------------------

def _draw_planet_at(
    surface: pygame.Surface,
    frame: list[int],
    cx: int,
    cy: int,
    color: tuple = _PLANET_COLOR,
) -> None:
    """Render one planet animation frame centred at virtual (cx, cy).

    32 source rows drawn at Y_SCALE=2 (each row → 2 screen rows).
    32 source bits scaled horizontally to 48 screen pixels (1.5×) via a
    Bresenham 3:2 step, so the rendered body is ~48 wide × ~64 tall screen
    pixels — appearing as a circular planet on the 640×480 display.
    """
    _OUT_W = 48
    sx0 = cx - _OUT_W // 2
    for row_idx, row in enumerate(frame):
        if row == 0:
            continue
        vy = cy - 16 + row_idx
        sy_base = vy * Y_SCALE
        if sy_base < 0 or sy_base + 1 >= SCREEN_H:
            continue
        for bit in range(32):
            if row & (1 << (31 - bit)):
                x0 = (bit * _OUT_W) // 32
                x1 = ((bit + 1) * _OUT_W) // 32
                if x0 == x1:
                    x1 = x0 + 1
                for bx in range(x0, x1):
                    sx = sx0 + bx
                    if 0 <= sx < SCREEN_W:
                        surface.set_at((sx, sy_base), color)
                        surface.set_at((sx, sy_base + 1), color)


def draw_planet(surface: pygame.Surface, state: GameState, attract: bool = False) -> None:
    """Draw animated planet centred on its position."""
    frame = get_planet_frame(state.planet_state)
    color = _NEON_PLT if state.neon_mode else _PLANET_COLOR
    if attract:
        from .constants import ATTRACT_PLANET_X, ATTRACT_PLANET_Y
        _draw_planet_at(surface, frame, ATTRACT_PLANET_X, ATTRACT_PLANET_Y, color)
    else:
        _draw_planet_at(surface, frame, PLANET_X, PLANET_Y, color)


# ---------------------------------------------------------------------------
# Ship and torpedo rendering
# ---------------------------------------------------------------------------

def draw_enterprise(surface: pygame.Surface, state: GameState) -> None:
    """Draw Enterprise ship (16×16 sprite)."""
    ship = state.objects[ENT_OBJ]
    if ship.eflg == EFLG_INACTIVE:
        return
    if ship.eflg == EFLG_EXPLODING:
        return   # scatter particles drawn by draw_hyper_particles
    if ship.flags & CLOAK_BIT:
        return   # cloaked — invisible
    bitmap = get_enterprise_sprite(ship.angle)
    if state.neon_mode:
        sx0 = ship.x - 8
        sy0 = ship.y * Y_SCALE - 8
        _blit_sprite_neon(surface, bitmap, 16, sx0, sy0, _NEON_ENT)
    else:
        draw_ship_sprite(surface, bitmap, ship.x, ship.y, _ENT_COLOR)
    ship.x_drawn = ship.x
    ship.y_drawn = ship.y
    ship.angle_drawn = ship.angle
    ship.uflg &= ~REDRAW_BIT


def draw_klingon(surface: pygame.Surface, state: GameState) -> None:
    """Draw Klingon ship (16×16 sprite)."""
    ship = state.objects[KLN_OBJ]
    if ship.eflg == EFLG_INACTIVE:
        return
    if ship.eflg == EFLG_EXPLODING:
        return   # scatter particles drawn by draw_hyper_particles
    if ship.flags & CLOAK_BIT:
        return
    bitmap = get_klingon_sprite(ship.angle)
    if state.neon_mode:
        sx0 = ship.x - 8
        sy0 = ship.y * Y_SCALE - 8
        _blit_sprite_neon(surface, bitmap, 16, sx0, sy0, _NEON_KLN)
    else:
        draw_ship_sprite(surface, bitmap, ship.x, ship.y, _KLN_COLOR)
    ship.x_drawn = ship.x
    ship.y_drawn = ship.y
    ship.angle_drawn = ship.angle
    ship.uflg &= ~REDRAW_BIT


def draw_torpedoes(surface: pygame.Surface, state: GameState) -> None:
    """Draw all active torpedoes."""
    for i in range(ENT_TORP_START, ENT_TORP_END):
        obj = state.objects[i]
        if obj.eflg == EFLG_ACTIVE:
            bitmap = get_enterprise_torp_sprite(obj.angle)
            if state.neon_mode:
                sx0 = obj.x - 4
                sy0 = obj.y * Y_SCALE - 4
                _blit_sprite_neon(surface, bitmap, 8, sx0, sy0, _NEON_ETOR)
            else:
                draw_sprite(surface, bitmap, obj.x, obj.y, _TORP_COLOR)
        elif obj.eflg == EFLG_EXPLODING:
            _draw_explosion(surface, obj)
    for i in range(KLN_TORP_START, KLN_TORP_END):
        obj = state.objects[i]
        if obj.eflg == EFLG_ACTIVE:
            bitmap = get_klingon_torp_sprite(obj.angle)
            if state.neon_mode:
                sx0 = obj.x - 4
                sy0 = obj.y * Y_SCALE - 4
                _blit_sprite_neon(surface, bitmap, 8, sx0, sy0, _NEON_KTOR)
            else:
                draw_sprite(surface, bitmap, obj.x, obj.y, _TORP_COLOR)
        elif obj.eflg == EFLG_EXPLODING:
            _draw_explosion(surface, obj)


def _draw_sprite_scaled(
    surface: pygame.Surface,
    bitmap: list[int],
    cx: int,
    cy: int,
    color: tuple,
    scale: int,
) -> None:
    """Draw an 8×8 bitmap at (scale)× magnification, centred at virtual (cx, cy).

    Each source bit becomes a scale×scale block of screen pixels.
    """
    half = 4 * scale            # half-size for centring
    sx0 = cx - half
    sy0 = cy * Y_SCALE - half
    for row_idx, row_bits in enumerate(bitmap):
        if row_bits == 0:
            continue
        for bit in range(8):
            if row_bits & (1 << (7 - bit)):
                for dr in range(scale):
                    sy = sy0 + row_idx * scale + dr
                    if sy < 0 or sy >= SCREEN_H:
                        continue
                    for dc in range(scale):
                        sx = sx0 + bit * scale + dc
                        if 0 <= sx < SCREEN_W:
                            surface.set_at((sx, sy), color)


def _draw_explosion(
    surface: pygame.Surface,
    obj,
    exps_start: int = 8,
    scale: int = 1,
) -> None:
    """Draw explosion animation frame for an object.

    Args:
        exps_start : initial exps value when explosion began (8 for torps,
                     SHIP_EXPLOSION_TICKS for ships).
        scale      : pixel scale factor (1 for torps, 3 for ships).
    """
    elapsed = exps_start - max(0, obj.exps)
    frame_idx = min(7, (elapsed * 8) // exps_start)
    bitmap = get_explosion_frame(frame_idx)
    if scale == 1:
        draw_sprite(surface, bitmap, obj.x, obj.y, _WHITE)
    else:
        _draw_sprite_scaled(surface, bitmap, obj.x, obj.y, _WHITE, scale)


# ---------------------------------------------------------------------------
# Hyperspace particles
# ---------------------------------------------------------------------------

def draw_hyper_particles(surface: pygame.Surface, state: GameState) -> None:
    """Draw scatter particles for both ships' hyperspace animations."""
    for flag_attr, particle_start, neon_color in (
        ('hyper_ent_flag', 0,  _NEON_PART_ENT),
        ('hyper_kln_flag', 32, _NEON_PART_KLN),
    ):
        if getattr(state, flag_attr) == 0:
            continue
        color = neon_color if state.neon_mode else _WHITE
        for p in state.hyper_particles[particle_start:particle_start + 32]:
            if p.active:
                vx = int(p.x)
                vy = int(p.y)
                put_pixel(surface, vx, vy, color)


# ---------------------------------------------------------------------------
# HUD — energy bars
# ---------------------------------------------------------------------------

def draw_energy_bars(surface: pygame.Surface, state: GameState) -> None:
    """Draw S and E energy bars for both ships at the bottom of the screen."""
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
    """Draw F1–F8 footer bar, highlighting active toggles."""
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
