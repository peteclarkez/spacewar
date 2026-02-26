"""attract.py — attract mode (title screen sequence).

Mirrors ATTRACT.ASM.

The original cycles through four screens:
  0 — Animated SPACEWAR title + copyright + scores
  1 — Game instructions
  2 — Key layout grid (3×3 box grid per player)
  3 — "User supported" message

Title animation
---------------
90 tile pieces scatter outward with random velocities then contract back to
spell SPACEWAR.  Mirrors placing_title / first_movement / move_title in
ATTRACT.ASM.  Tile bitmaps are transcribed from SPSET8.ASM (character
indices 0x0E–0x12).

Key grid
--------
Two 3×3 bordered-box grids, one per player, mirroring the key_instructions
proc in ATTRACT.ASM which uses box-drawing tile characters to build the grid.

Public API
----------
AttractState — dataclass tracking screen index, timer, and title animation
run_attract_tick(state, attract, surface, key_state) -> int
draw_attract_screen(surface, state, attract)
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

import pygame

from .constants import (
    MODE_PLAY, MODE_ATTRACT,
    ATTRACT_SCREENS, ATTRACT_CYCLE_TIME,
    SCREEN_W, SCREEN_H, Y_SCALE,
    ATTRACT_PLANET_X, ATTRACT_PLANET_Y,
    PLANET_TIME,
)

# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------
_BLACK  = (0,   0,   0)
_WHITE  = (255, 255, 255)
_DIM    = (128, 128, 128)
_GREEN  = (0,   200, 0)
_YELLOW = (200, 200, 0)

# ---------------------------------------------------------------------------
# Title animation constants  (ATTRACT.ASM / GENERAL.EQU, CGA mode)
# ---------------------------------------------------------------------------
_TW = 16    # TITLE_WIDTH  — tile width in virtual pixels (same Hercules + CGA)
_TH = 8     # TITLE_HEIGTH — tile height in virtual pixels (CGA value)

# CGA title grid origin:
#   MAX_X_TITLES = 640/16 = 40,  MAX_Y_TITLES = 200/8 = 25
#   TBX = (40 - 8*4) / 2 = 4,   TBY = (25 - 5) / 2 = 10
_TBX = 4
_TBY = 10

# Phase labels for the scatter/assemble state machine.
_PHASE_HOLD     = 0   # pieces at target positions; count-down
_PHASE_SCATTER  = 1   # pieces moving outward for _SCATTER_TICKS ticks
_PHASE_ASSEMBLE = 2   # pieces returning for _SCATTER_TICKS ticks

_SCATTER_TICKS = 45   # TITLE_MOVE_COUNT — steps per scatter / return pass
_HOLD_TICKS    = 135  # frames to display assembled title before scattering

# ---------------------------------------------------------------------------
# Tile bitmaps  (SPSET8.ASM, types 0x0E–0x12)
# Each entry is 8 × 16-bit row values; MSB of each word = leftmost pixel.
# ---------------------------------------------------------------------------
_TILE_ROWS: dict[int, list[int]] = {
    0x0E: [0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF,
           0xFFFF, 0xFFFF, 0xFFFF, 0xFFFF],  # solid fill ■
    0x0F: [0x0003, 0x000F, 0x003F, 0x00FF,
           0x03FF, 0x0FFF, 0x3FFF, 0xFFFF],  # lower-right triangle ◢
    0x10: [0xC000, 0xF000, 0xFC00, 0xFF00,
           0xFFC0, 0xFFF0, 0xFFFC, 0xFFFF],  # lower-left triangle  ◣
    0x11: [0xFFFF, 0xFFFC, 0xFFF0, 0xFFC0,
           0xFF00, 0xFC00, 0xF000, 0xC000],  # upper-left triangle  ◤
    0x12: [0xFFFF, 0x3FFF, 0x0FFF, 0x03FF,
           0x00FF, 0x003F, 0x000F, 0x0003],  # upper-right triangle ◥
}

# Lazy cache: tile_type → pygame.Surface (16 × _TH*Y_SCALE screen pixels)
_tile_cache: dict[int, pygame.Surface] = {}


def _get_tile_surface(tile_type: int) -> pygame.Surface:
    """Return (or build) a screen-resolution surface for *tile_type*."""
    if tile_type not in _tile_cache:
        rows = _TILE_ROWS[tile_type]
        h = _TH * Y_SCALE
        surf = pygame.Surface((16, h))
        surf.fill(_BLACK)
        for row_idx, bits in enumerate(rows):
            for col in range(16):
                if bits & (0x8000 >> col):
                    y0 = row_idx * Y_SCALE
                    surf.set_at((col, y0), _WHITE)
                    if Y_SCALE > 1:
                        surf.set_at((col, y0 + 1), _WHITE)
        _tile_cache[tile_type] = surf
    return _tile_cache[tile_type]


# ---------------------------------------------------------------------------
# Title piece table — (type, target_x, target_y) in virtual coordinates.
# Transcribed from ATTRACT.ASM TITLE_TYPE + TITLE_X + TITLE_Y (CGA values).
#
# Letter offsets (TX = column index × _TW):
#   S at TBX+0=4, P at +4=8, A at +8=12, C at +12=16, E at +16=20,
#   W at +20=24 (5 cols wide → +5 gap),
#   A at +25=29, R at +29=33.
# ---------------------------------------------------------------------------
def _build_title_pieces() -> list[tuple[int, int, int]]:
    TW, TH = _TW, _TH
    B, R   = _TBX, _TBY
    pieces: list[tuple[int, int, int]] = []

    letters = [
        # (types,  col-offsets,           row-offsets,            col-base)
        # S — 11 pieces
        ([0x0F, 0x0E, 0x11, 0x0E, 0x10, 0x0E, 0x12, 0x0E, 0x0F, 0x0E, 0x11],
         [0, 1, 2, 2, 2, 1, 0, 0, 0, 1, 2],
         [4, 4, 4, 3, 2, 2, 2, 1, 0, 0, 0],
         B + 0),
        # P — 9 pieces
        ([0x11, 0x0E, 0x0E, 0x0E, 0x0F, 0x0E, 0x10, 0x0E, 0x11],
         [0, 0, 0, 0, 0, 1, 2, 2, 2],
         [4, 3, 2, 1, 0, 0, 0, 1, 2],
         B + 4),
        # A — 12 pieces
        ([0x11, 0x0E, 0x0E, 0x0E, 0x0F, 0x0E, 0x11, 0x0E, 0x0E, 0x0E, 0x0E, 0x11],
         [0, 0, 0, 0, 0, 1, 2, 2, 2, 1, 2, 2],
         [4, 3, 2, 1, 0, 0, 0, 1, 2, 2, 3, 4],
         B + 8),
        # C — 9 pieces
        ([0x11, 0x0E, 0x12, 0x0E, 0x0E, 0x0E, 0x0F, 0x0E, 0x11],
         [2, 1, 0, 0, 0, 0, 0, 1, 2],
         [4, 4, 4, 3, 2, 1, 0, 0, 0],
         B + 12),
        # E — 10 pieces
        ([0x11, 0x0E, 0x12, 0x0E, 0x0E, 0x11, 0x0E, 0x0F, 0x0E, 0x11],
         [2, 1, 0, 0, 0, 1, 0, 0, 1, 2],
         [4, 4, 4, 3, 2, 2, 1, 0, 0, 0],
         B + 16),
        # W — 14 pieces  (W spans cols 0–3; TX06 = TX05+5 leaves a 1-col gap)
        ([0x0F, 0x0E, 0x0E, 0x0E, 0x11, 0x12, 0x10, 0x0F, 0x11, 0x12, 0x0E, 0x0E, 0x0E, 0x0F],
         [3, 3, 3, 3, 3, 2, 2, 1, 1, 0, 0, 0, 0, 0],
         [0, 1, 2, 3, 4, 4, 3, 3, 4, 4, 3, 2, 1, 0],
         B + 20),
        # A — 12 pieces  (TX06 = 24+5 = 29)
        ([0x11, 0x0E, 0x0E, 0x0E, 0x0F, 0x0E, 0x11, 0x0E, 0x0E, 0x0E, 0x0E, 0x11],
         [0, 0, 0, 0, 0, 1, 2, 2, 2, 1, 2, 2],
         [4, 3, 2, 1, 0, 0, 0, 1, 2, 2, 3, 4],
         B + 25),
        # R — 13 pieces  (TX07 = 29+4 = 33)
        ([0x11, 0x0E, 0x0E, 0x0E, 0x0F, 0x0E, 0x10, 0x0E, 0x11, 0x10, 0x12, 0x10, 0x12],
         [0, 0, 0, 0, 0, 1, 2, 2, 2, 1, 1, 2, 2],
         [4, 3, 2, 1, 0, 0, 0, 1, 2, 2, 3, 3, 4],
         B + 29),
    ]

    for types, cols, rows, tx_base in letters:
        for t, c, r in zip(types, cols, rows):
            pieces.append((t, TW * (c + tx_base), TH * (r + R)))

    return pieces


_TITLE_PIECES: list[tuple[int, int, int]] = _build_title_pieces()
_TOTAL_PIECES: int = len(_TITLE_PIECES)   # 90


# ---------------------------------------------------------------------------
# TitleAnimation dataclass
# ---------------------------------------------------------------------------
@dataclass
class TitleAnimation:
    """Per-piece state for the SPACEWAR letter-block particle animation.

    Mirrors the TITLE_X_DIS / TITLE_Y_DIS / TITLE_X_VEL / TITLE_Y_VEL arrays
    from ATTRACT.ASM.  Initial state is fully assembled (HOLD phase).
    """
    phase:      int = _PHASE_HOLD
    phase_tick: int = 0
    pos_x: list[float] = field(
        default_factory=lambda: [float(p[1]) for p in _TITLE_PIECES])
    pos_y: list[float] = field(
        default_factory=lambda: [float(p[2]) for p in _TITLE_PIECES])
    vel_x: list[float] = field(
        default_factory=lambda: [0.0] * _TOTAL_PIECES)
    vel_y: list[float] = field(
        default_factory=lambda: [0.0] * _TOTAL_PIECES)


def _tick_title_anim(anim: TitleAnimation) -> None:
    """Advance the title particle animation by one game tick.

    Phase machine mirrors first_movement / move_title in ATTRACT.ASM:
      HOLD (assembled) → SCATTER (outward, 30 steps)
                       → ASSEMBLE (return, 30 steps)
                       → HOLD → …

    Scatter velocity ≈ ±4 virtual px/tick  (matches ASM's signed-16-bit
    random * 8 / 65536 ≈ ±4 px/step for a full-range random value).
    """
    if anim.phase == _PHASE_HOLD:
        anim.phase_tick += 1
        if anim.phase_tick >= _HOLD_TICKS:
            for i in range(_TOTAL_PIECES):
                anim.vel_x[i] = random.uniform(-2.67, 2.67)
                anim.vel_y[i] = random.uniform(-2.67, 2.67)
            anim.phase     = _PHASE_SCATTER
            anim.phase_tick = 0

    elif anim.phase == _PHASE_SCATTER:
        for i in range(_TOTAL_PIECES):
            anim.pos_x[i] += anim.vel_x[i]
            anim.pos_y[i] += anim.vel_y[i]
        anim.phase_tick += 1
        if anim.phase_tick >= _SCATTER_TICKS:
            # Reverse velocities so pieces travel back toward origin.
            for i in range(_TOTAL_PIECES):
                anim.vel_x[i] = -anim.vel_x[i]
                anim.vel_y[i] = -anim.vel_y[i]
            anim.phase     = _PHASE_ASSEMBLE
            anim.phase_tick = 0

    else:  # _PHASE_ASSEMBLE
        for i in range(_TOTAL_PIECES):
            anim.pos_x[i] += anim.vel_x[i]
            anim.pos_y[i] += anim.vel_y[i]
        anim.phase_tick += 1
        if anim.phase_tick >= _SCATTER_TICKS:
            # Snap to exact target positions and start holding.
            for i, (_, tx, ty) in enumerate(_TITLE_PIECES):
                anim.pos_x[i] = float(tx)
                anim.pos_y[i] = float(ty)
            anim.phase     = _PHASE_HOLD
            anim.phase_tick = 0


# ---------------------------------------------------------------------------
# AttractState
# ---------------------------------------------------------------------------
@dataclass
class AttractState:
    """Attract mode display state."""
    screen_index: int          = 0
    screen_timer: int          = 0
    title_anim:   TitleAnimation = field(default_factory=TitleAnimation)


# ---------------------------------------------------------------------------
# Public API — run_attract_tick
# ---------------------------------------------------------------------------
def run_attract_tick(
    state,
    attract: AttractState,
    surface: pygame.Surface,
    key_state,
) -> int:
    """Advance attract mode by one tick.

    Returns new game mode (MODE_ATTRACT or MODE_PLAY).
    Mirrors attract-mode sequencing in ATTRACT.ASM.
    """
    # Advance blink + planet animation (run_physics_tick not called here).
    state.blink = (state.blink + 1) & 0xFF
    if (state.blink & (PLANET_TIME - 1)) == 0:
        state.planet_state = (state.planet_state + 1) & 0x0F

    # Cycle attract screens.
    attract.screen_timer += 1
    if attract.screen_timer >= ATTRACT_CYCLE_TIME:
        attract.screen_timer = 0
        attract.screen_index = (attract.screen_index + 1) % ATTRACT_SCREENS
        if attract.screen_index == 0:
            # Reset animation to assembled state on each return to title screen.
            attract.title_anim = TitleAnimation()

    # Advance title animation only while on the title screen.
    if attract.screen_index == 0:
        _tick_title_anim(attract.title_anim)

    # F2 starts the game.
    if key_state.just_pressed.get(pygame.K_F2):
        from .init import reset_game_objects
        reset_game_objects(state)
        state.pause_enable = False
        state.game_mode = MODE_PLAY
        return MODE_PLAY

    return MODE_ATTRACT


# ---------------------------------------------------------------------------
# Public API — draw_attract_screen
# ---------------------------------------------------------------------------
def draw_attract_screen(
    surface: pygame.Surface,
    state,
    attract: AttractState,
) -> None:
    """Render the current attract screen.

    Mirrors the screen-drawing sections of ATTRACT.ASM.
    """
    surface.fill(_BLACK)

    idx = attract.screen_index
    if idx == 0:
        _draw_title_screen(surface, state, attract)
    elif idx == 1:
        _draw_instructions(surface)
    elif idx == 2:
        _draw_key_grid(surface)
    else:
        _draw_user_supported(surface)

    # Animated planet in top-right corner (all attract screens).
    _draw_attract_planet(surface, state)


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------
def _font(size: int) -> pygame.font.Font:
    return pygame.font.SysFont('monospace', size)


def _centred(surface: pygame.Surface, text: str, y: int,
             color=_WHITE, size: int = 20) -> None:
    surf = _font(size).render(text, True, color)
    surface.blit(surf, ((SCREEN_W - surf.get_width()) // 2, y))


def _text(surface: pygame.Surface, text: str, x: int, y: int,
          color=_WHITE, size: int = 16) -> None:
    surface.blit(_font(size).render(text, True, color), (x, y))


# ---------------------------------------------------------------------------
# Screen 0 — animated SPACEWAR title + copyright + scores
# ---------------------------------------------------------------------------
def _draw_title_screen(
    surface: pygame.Surface,
    state,
    attract: AttractState,
) -> None:
    """Attract screen 0: animated title, copyright, scores.

    Mirrors display_copyright + placing_title / move_title in ATTRACT.ASM.
    """
    _draw_title_anim(surface, attract.title_anim)

    _centred(surface, 'V1.72',                          260, _DIM, 16)
    _centred(surface, 'COPYRIGHT \u00a9 1985  B SEILER', 282, _DIM, 16)

    ent_score = getattr(state, 'enterprise_score', 0)
    kln_score = getattr(state, 'klingon_score',    0)
    _text(surface, f'ENTERPRISE: {ent_score}', 130, 325, _GREEN,  18)
    _text(surface, f'KLINGON:    {kln_score}',  370, 325, _YELLOW, 18)

    _centred(surface, 'PRESS F2 TO PLAY', 395, _WHITE, 20)


def _draw_title_anim(surface: pygame.Surface, anim: TitleAnimation) -> None:
    """Draw all 90 title tile pieces at their current (animated) positions.

    Maps virtual coordinates to screen coordinates (y × Y_SCALE) and blits
    each pre-built 16×(TH*Y_SCALE) surface tile.
    """
    for i, (tile_type, _, _) in enumerate(_TITLE_PIECES):
        px = int(anim.pos_x[i])
        py = int(anim.pos_y[i])
        surface.blit(_get_tile_surface(tile_type), (px, py * Y_SCALE))


# ---------------------------------------------------------------------------
# Screen 1 — game instructions
# ---------------------------------------------------------------------------
def _draw_instructions(surface: pygame.Surface) -> None:
    """Attract screen 1: game instructions.

    Mirrors game_instructions in ATTRACT.ASM (text reproduced verbatim).
    """
    _centred(surface, 'G A M E    I N S T R U C T I O N S', 16, _WHITE, 20)
    pygame.draw.line(surface, _DIM, (40, 44), (SCREEN_W - 40, 44), 1)

    lines = [
        ('OBJECT: Destroy the other ship with PHOTON TORPEDOS or',         _WHITE),
        ('        PHASERS until all its SHIELD energy is gone.',            _DIM),
        ('', None),
        ('WEAPONS: PHOTON TORPEDOS - Use = 1 unit, Damage = 4 units.',     _WHITE),
        ('         PHASERS         - Use = 1 unit, Damage = 2 units.',      _DIM),
        ('', None),
        ('DEFENSE: IMPULSE ENGINES - Use = 1 unit every 1/2 second.',      _WHITE),
        ('         CLOAK           - Use = 1 unit every 1/2 second.',       _DIM),
        ('         HYPER SPACE     - Use = 8 units.',                       _DIM),
        ('', None),
        ('COMMENT: You must have energy to use WEAPONS or DEFENCES.',       _WHITE),
        ('         ENERGY is recharged at 1 unit every 2 seconds.',         _DIM),
        ('         Use PHASERS to shoot incoming PHOTON TORPEDOS.',         _DIM),
        ('         The WARNING sound indicates SHIELD power too low.',       _DIM),
        ('         Touching the PLANET will drain your SHIELDS.',           _DIM),
        ('         The Left Robot player is defensive.',                    _DIM),
        ('         The Right Robot player is offensive.',                   _DIM),
        ('         Function key 8 toggles sound on or off.',                _DIM),
    ]

    y = 60
    for text, color in lines:
        if text == '':
            y += 8
        else:
            _text(surface, text, 16, y, color, 14)
            y += 18

    _centred(surface, 'PRESS F2 TO PLAY', 408, _WHITE, 18)


# ---------------------------------------------------------------------------
# Screen 2 — key layout grid
# ---------------------------------------------------------------------------
# Cell content: (key_label, function_line_1, function_line_2)
_LEFT_KEYS: list[tuple[str, str, str]] = [
    ('Q', 'FIRE',    'PHASERS'),
    ('W', '',        'CLOAK'),
    ('E', 'FIRE',    'PHOTONS'),
    ('A', 'ROTATE',  'CCW'),
    ('S', 'IMPULSE', 'ENGINES'),
    ('D', 'ROTATE',  'CW'),
    ('Z', 'WEAPON',  'ENERGY'),
    ('X', 'HYPER',   'SPACE'),
    ('C', 'SHIELD',  'ENERGY'),
]

_RIGHT_KEYS: list[tuple[str, str, str]] = [
    ('7', 'FIRE',    'PHASERS'),
    ('8', '',        'CLOAK'),
    ('9', 'FIRE',    'PHOTONS'),
    ('4', 'ROTATE',  'CCW'),
    ('5', 'IMPULSE', 'ENGINES'),
    ('6', 'ROTATE',  'CW'),
    ('1', 'WEAPON',  'ENERGY'),
    ('2', 'HYPER',   'SPACE'),
    ('3', 'SHIELD',  'ENERGY'),
]

# Grid geometry.  Two 3-column grids are laid out symmetrically:
#   margin(40) + left_grid(3×CELL_W) + gap + right_grid(3×CELL_W) + margin(40)
_CELL_W = 78
_CELL_H = 65
_GRID_W = _CELL_W * 3   # 234 px
_LX     = 40            # left grid x origin
_RX     = SCREEN_W - 40 - _GRID_W  # right grid x origin  (= 366)


def _draw_key_cell(
    surface: pygame.Surface,
    x: int, y: int,
    key_label: str, line1: str, line2: str,
) -> None:
    """Draw one bordered key-button cell at screen position (x, y).

    Mirrors the double-line box-drawing tiles (0x14–0x1E) from SPSET8.ASM.
    The double-line effect is approximated with two concentric white rectangles.
    """
    rect = pygame.Rect(x, y, _CELL_W, _CELL_H)
    pygame.draw.rect(surface, _WHITE, rect, 1)
    pygame.draw.rect(surface, _WHITE, rect.inflate(-4, -4), 1)

    # Key label — large, yellow, centred near top.
    fk  = _font(20)
    ks  = fk.render(f'[{key_label}]', True, _YELLOW)
    surface.blit(ks, (x + (_CELL_W - ks.get_width()) // 2, y + 5))

    # Function description lines — small, white, centred below key label.
    ff = _font(12)
    if line1:
        s1 = ff.render(line1, True, _WHITE)
        surface.blit(s1, (x + (_CELL_W - s1.get_width()) // 2, y + 31))
    if line2:
        s2 = ff.render(line2, True, _WHITE)
        surface.blit(s2, (x + (_CELL_W - s2.get_width()) // 2, y + 47))


def _draw_key_grid(surface: pygame.Surface) -> None:
    """Attract screen 2: key-binding grid.

    Mirrors key_instructions in ATTRACT.ASM.  Two 3×3 grids of bordered cells
    (left player QWEASDZXC, right player keypad 789456123) with ship-icon
    decorations above each grid header, as in the original.
    """
    from .pictures import get_enterprise_sprite, get_klingon_sprite

    # --- Title bar ---
    _centred(surface, 'G A M E    K E Y S', 12, _WHITE, 20)
    pygame.draw.line(surface, _DIM, (40, 40), (SCREEN_W - 40, 40), 1)

    grid_y   = 95
    label_y  = grid_y - 26

    # --- Player labels ---
    _text(surface, 'LEFT PLAYER KEYS',  _LX,      label_y, _WHITE, 14)
    _text(surface, 'RIGHT PLAYER KEYS', _RX,      label_y, _WHITE, 14)

    # --- Ship sprite icons (16×16, drawn at screen coords) ---
    ent_spr = get_enterprise_sprite(0)    # angle 0 = pointing right
    kln_spr = get_klingon_sprite(128)     # angle 128 = pointing left (as in original)
    _blit_ship(surface, ent_spr, _LX + _GRID_W + 4, label_y - 2)
    _blit_ship(surface, kln_spr, _RX + _GRID_W + 4, label_y - 2)

    # --- Left 3×3 grid ---
    for idx, (key_label, line1, line2) in enumerate(_LEFT_KEYS):
        row, col = divmod(idx, 3)
        _draw_key_cell(surface,
                       _LX + col * _CELL_W, grid_y + row * _CELL_H,
                       key_label, line1, line2)

    # --- Right 3×3 grid ---
    for idx, (key_label, line1, line2) in enumerate(_RIGHT_KEYS):
        row, col = divmod(idx, 3)
        _draw_key_cell(surface,
                       _RX + col * _CELL_W, grid_y + row * _CELL_H,
                       key_label, line1, line2)

    _centred(surface, 'PRESS F2 TO PLAY', 408, _WHITE, 18)


def _blit_ship(
    surface: pygame.Surface,
    bitmap: list[int],
    sx: int,
    sy: int,
) -> None:
    """Blit a 16×16 ship sprite at screen pixel (sx, sy) top-left corner.

    Used on the key-layout screen where sprites are decorative headers
    (not subject to the virtual-coordinate Y_SCALE transform).
    Bit 15 of each 16-bit row word = leftmost pixel.
    """
    for row, bits in enumerate(bitmap):
        for col in range(16):
            if bits & (0x8000 >> col):
                surface.set_at((sx + col, sy + row), _WHITE)


# ---------------------------------------------------------------------------
# Screen 3 — user-supported message
# ---------------------------------------------------------------------------
def _draw_user_supported(surface: pygame.Surface) -> None:
    """Attract screen 3: user-supported message.

    Mirrors user_supported in ATTRACT.ASM (text reproduced verbatim).
    """
    _centred(surface, 'SPACEWAR', 55, _WHITE, 44)

    lines = [
        'SPACEWAR is distributed under the USER-SUPPORTED',
        'concept.  You are encouraged to copy and share this',
        'program with other users.  If you enjoy SPACEWAR, and want me',
        "to finish SPACE MINEZ your contribution ($20 suggested) will",
        'be appreciated.  For a $30 contribution you will receive the',
        'source code for latest version of SPACEWAR.',
        '',
        'USER-SUPPORTED software is based on these three beliefs:',
        ' 1.  The value of software is best assessed by the',
        '     user on his own system.',
        ' 2.  Creation of personal computer software can and',
        '     should be supported by computing community.',
        ' 3.  That copying of programs should be encouraged,',
        '     rather than restricted.',
        '',
        'Bill Seiler == 317 Lockewood Lane == Scotts Valley, CA. 95066',
    ]

    y = 145
    for line in lines:
        if line == '':
            y += 8
        else:
            _text(surface, line, 8, y, _DIM, 13)
            y += 17

    _centred(surface, 'PRESS F2 TO PLAY', 408, _WHITE, 18)


# ---------------------------------------------------------------------------
# Attract planet (top-right corner, all screens)
# ---------------------------------------------------------------------------
def _draw_attract_planet(surface: pygame.Surface, state) -> None:
    """Draw animated planet in top-right corner (mirrors ATTRACT.ASM interrupt)."""
    from .draw import draw_planet
    draw_planet(surface, state, attract=True)
