"""
Pixel-exact sprite data and Pygame surface generation for SpaceWar 1985.

Source bitmaps are given as ASCII art where '#' = lit pixel, '.' = dark.
Ships have 16 rotation frames (16 angle-units apart, 360/16 = 22.5°).
Torpedoes have 8 rotation frames (32 angle-units apart).
All surfaces are pre-built at import time if Pygame is available.
"""

from __future__ import annotations
import math
from typing import Sequence

# ── Raw source bitmaps ────────────────────────────────────────────────────────

# Enterprise 16×16, frame 0 (angle 0, pointing East / right)
_ENT_SRC = (
    ".....######.....",
    "...##......##...",
    "..#..........#..",
    ".##...........#.",
    "..##..........#.",
    "...##..........#",
    "....##.##......#",
    ".....##..#######",
    ".....##..#######",
    "....##.##......#",
    "...##..........#",
    "..##..........#.",
    ".##...........#.",
    "..#..........#..",
    "...##......##...",
    ".....######.....",
)

# Klingon 16×16, frame 8 → this is the EAST-facing canonical sprite
# (frame 8 in the original 16-frame sheet = angle 0 East for Klingon)
_KLN_SRC = (
    "..........##....",
    "......####..#...",
    ".....#####..#...",
    "....##....##....",
    "...##...........",
    "..##............",
    ".##....##.......",
    "#######..#......",
    "#######..#......",
    ".##....##.......",
    "..##............",
    "...##...........",
    "....##....##....",
    ".....#####..#...",
    "......####..#...",
    "..........##....",
)

# Enterprise torpedo 8×8, frame 0 (pointing East)
_ETORP_SRC = (
    "........",
    "##......",
    "..######",
    "..######",
    "##......",
    "........",
    "........",
    "........",
)

# Klingon torpedo 8×8, frame 4 (pointing West — we flip to get canonical East)
_KTORP_WEST = (
    "....###.",
    "..###...",
    "####....",
    "####....",
    "..###...",
    "....###.",
    "........",
    "........",
)

# Planet 32×32, frame 0
_PLANET_SRC = (
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
    "............########............",
    ".........###........###.........",
    ".......##..............##.......",
    ".....######################.....",
    "....#......................#....",
    "...#........................#...",
    "..############################..",
    ".#............................#.",
    ".#............................#.",
    "################################",
    "#..............................#",
    "#..............................#",
    "################################",
    ".#............................#.",
    ".######.......................#.",
    ".#.....#######################..",
    "#.......#...................#...",
    "#.......#..................#....",
    "#.......###################.....",
    ".#.....##..............##.......",
    "..#####..###........###.........",
    "............########............",
    "................................",
    "................................",
    "................................",
    "................................",
    "................................",
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse(rows: Sequence[str]) -> list[list[bool]]:
    """Convert ASCII art rows to a 2-D bool grid."""
    return [[ch == "#" for ch in row] for row in rows]


def _flip_h(grid: list[list[bool]]) -> list[list[bool]]:
    """Flip a pixel grid horizontally."""
    return [list(reversed(row)) for row in grid]


def _rotate_grid(grid: list[list[bool]], degrees: float) -> list[list[bool]]:
    """
    Rotate a square pixel grid by the given angle (degrees, CCW in math coords).
    Returns a new grid of the same size, with nearest-neighbour sampling.
    """
    size = len(grid)
    cx = cy = (size - 1) / 2.0
    rad = math.radians(degrees)
    cos_r = math.cos(rad)
    sin_r = math.sin(rad)
    result = [[False] * size for _ in range(size)]
    for dy in range(size):
        for dx in range(size):
            # Vector from centre in destination
            fx = dx - cx
            fy = dy - cy
            # Rotate back to source (inverse rotation)
            sx = fx * cos_r + fy * sin_r + cx
            sy = -fx * sin_r + fy * cos_r + cy
            si = int(round(sy))
            sj = int(round(sx))
            if 0 <= si < size and 0 <= sj < size:
                result[dy][dx] = grid[si][sj]
    return result


# ── Pygame surface builders ────────────────────────────────────────────────────

def _make_surface(grid: list[list[bool]], colour: tuple[int, int, int] = (255, 255, 255)):
    """Build a pygame.Surface with a transparent background from a bool grid."""
    import pygame
    h = len(grid)
    w = len(grid[0]) if h else 0
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))
    for y, row in enumerate(grid):
        for x, lit in enumerate(row):
            if lit:
                surf.set_at((x, y), colour + (255,))
    return surf


def _make_rotated_frames(
    grid: list[list[bool]],
    n_frames: int,
    colour: tuple[int, int, int] = (255, 255, 255),
) -> list:
    """
    Pre-render n_frames rotated versions of grid.
    Frame 0 = canonical East-facing (angle 0).
    Frame i = rotated by i * (360 / n_frames) degrees CCW (screen: CW in Y-down).

    In screen coords (Y-down), increasing angle → clockwise rotation visually,
    but pygame.transform.rotate uses CCW convention. We therefore negate.
    """
    import pygame
    base_surf = _make_surface(grid, colour)
    frames = []
    for i in range(n_frames):
        # Angle in 256-unit system; convert to degrees
        angle_256 = i * (256 // n_frames)
        # Screen rotation: angle 0=East, 64=Down, 128=West, 192=Up
        # pygame.transform.rotate rotates CCW in screen coords.
        # To rotate CW (towards South) for positive angles → negate.
        deg = -(angle_256 / 256.0 * 360.0)
        rotated = pygame.transform.rotate(base_surf, deg)
        frames.append(rotated)
    return frames


# ── Public sprite cache ───────────────────────────────────────────────────────

_cache: dict[str, list] = {}


def build_sprites(neon: bool = False) -> None:
    """
    Pre-build all sprite frames into the module cache.
    Must be called after pygame.display.init().
    neon=True adds coloured glow halos.
    """
    from spacewar import constants as C

    colour = C.WHITE

    ent_grid   = _parse(_ENT_SRC)
    kln_grid   = _parse(_KLN_SRC)
    etorp_grid = _parse(_ETORP_SRC)
    # Canonical East-facing Klingon torpedo = horizontal flip of the West sprite
    ktorp_grid = _flip_h(_parse(_KTORP_WEST))
    planet_grid = _parse(_PLANET_SRC)

    ent_col   = C.NEON_ENT_GLOW  if neon else colour
    kln_col   = C.NEON_KLN_GLOW  if neon else colour
    etorp_col = C.NEON_ETORP_GLOW if neon else colour
    ktorp_col = C.NEON_KTORP_GLOW if neon else colour
    planet_col= C.NEON_PLANET    if neon else colour

    _cache["ent"]   = _make_rotated_frames(ent_grid,   16, ent_col)
    _cache["kln"]   = _make_rotated_frames(kln_grid,   16, kln_col)
    _cache["etorp"] = _make_rotated_frames(etorp_grid,  8, etorp_col)
    _cache["ktorp"] = _make_rotated_frames(ktorp_grid,  8, ktorp_col)
    _cache["neon"]  = [neon]

    # Planet: scale 32×32 source → 48×64 screen pixels
    planet_surf = _make_surface(planet_grid, planet_col)
    import pygame
    _cache["planet"] = pygame.transform.scale(planet_surf, (C.PLANET_DRAW_W, C.PLANET_DRAW_H))


def get_ship_frame(player: int, angle_256: int):
    """Return the pygame.Surface for the given ship and 256-unit angle."""
    key = "ent" if player == 0 else "kln"
    frames = _cache[key]
    frame_idx = (angle_256 // 16) % 16
    return frames[frame_idx]


def get_torp_frame(player: int, angle_256: int):
    """Return the pygame.Surface for a torpedo at the given 256-unit angle."""
    key = "etorp" if player == 0 else "ktorp"
    frames = _cache[key]
    frame_idx = (angle_256 // 32) % 8
    return frames[frame_idx]


def get_planet_surface():
    """Return the pre-scaled planet pygame.Surface."""
    return _cache.get("planet")


def draw_sprite_centered(surface, sprite_surf, vx: float, vy: float) -> None:
    """
    Blit a sprite onto surface centred at virtual coords (vx, vy).
    Y is scaled by Y_SCALE for display.
    """
    from spacewar.constants import Y_SCALE
    sx = int(vx) - sprite_surf.get_width() // 2
    sy = int(vy) * Y_SCALE - sprite_surf.get_height() // 2
    surface.blit(sprite_surf, (sx, sy))


def draw_neon_sprite(surface, sprite_surf, vx: float, vy: float, glow_col: tuple) -> None:
    """
    Two-pass neon blit: glow halo (8 neighbours) then white-hot core.
    """
    import pygame
    from spacewar.constants import Y_SCALE, WHITE

    sx = int(vx) - sprite_surf.get_width() // 2
    sy = int(vy) * Y_SCALE - sprite_surf.get_height() // 2

    # Halo pass: recolour sprite to glow colour
    halo = sprite_surf.copy()
    # Replace white pixels with glow colour
    px_arr = pygame.PixelArray(halo)
    white_key = halo.map_rgb(255, 255, 255)
    glow_key  = halo.map_rgb(*glow_col)
    px_arr.replace(white_key, glow_key)
    del px_arr
    halo.set_alpha(128)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx or dy:
                surface.blit(halo, (sx + dx, sy + dy))

    # Core pass: white
    surface.blit(sprite_surf, (sx, sy))
