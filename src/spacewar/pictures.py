"""pictures.py — sprite and animation data.

Mirrors PICTURES.ASM / PICT8.ASM / SPSET.ASM.

Each sprite is stored as a list of ints, one per row, where each bit
represents a pixel (MSB = leftmost pixel, 8 pixels wide).

The original game has hand-crafted 8×8 ship sprites for 64 rotations
(every 4th of the 256-step circle).  For this initial version, sprites
are generated procedurally and marked # TODO: transcribe from PICT8.ASM.

Public API
----------
get_enterprise_sprite(angle) -> list[int]   8-row bitmasks
get_klingon_sprite(angle)    -> list[int]
get_explosion_frame(n)       -> list[int]   n = 0..7
get_planet_frame(n)          -> list[int]   n = 0..15, 16×16 bitmask rows
"""

from __future__ import annotations

import math

# ---------------------------------------------------------------------------
# Ship sprite generation
# ---------------------------------------------------------------------------
# The 256-step angle system: 0=right, 64=down, 128=left, 192=up.
# Sprites are generated for every 4th angle (64 sprites = 256/4).
# Each sprite is 8×8 pixels stored as 8 ints (bit 7 = left pixel).

_SPRITE_ANGLES = 64       # number of pre-rotated sprites
_SPRITE_SIZE = 8          # 8×8 pixels


def _make_ship_bitmap(angle_256: int, facing: str = 'triangle') -> list[int]:
    """Generate an 8×8 Enterprise sprite for the given 256-step angle.

    Base shape points RIGHT (angle=0): fish/arrow with nacelles at the rear.
    Bit layout: MSB (0x80) = leftmost screen pixel, LSB (0x01) = rightmost.
    With centre cx=3.5, col vx = cx-4+bit, so:
      0x60 → cols cx-3, cx-2 (rear nacelles)
      0x7C → cols cx-3..cx+1 (tapered hull)
      0x7F → cols cx-3..cx+3 (full hull, rightmost = nose)

    # TODO: transcribe exact bitmaps from PICT8.ASM for pixel-perfect fidelity.
    """
    # Enterprise pointing right: elongated body, wider nacelles at rear
    base_ent = [0x00, 0x60, 0x7C, 0x7F, 0x7C, 0x60, 0x00, 0x00]
    angle_deg = angle_256 * 360.0 / 256.0
    return _rotate_bitmap(base_ent, angle_deg)


def _make_klingon_bitmap(angle_256: int) -> list[int]:
    """Generate an 8×8 Klingon ship sprite.

    Base shape points RIGHT (angle=0): bird-of-prey with wide swept-back wings.
      0xF0 → cols cx-4..cx-1 (wide wings at rear, 4 pixels)
      0x7E → cols cx-3..cx+2 (body)
      0x7F → cols cx-3..cx+3 (full hull, rightmost = nose)

    # TODO: transcribe exact bitmaps from PICT8.ASM for pixel-perfect fidelity.
    """
    base_kln = [0x00, 0xF0, 0x7E, 0x7F, 0x7E, 0xF0, 0x00, 0x00]
    angle_deg = angle_256 * 360.0 / 256.0
    return _rotate_bitmap(base_kln, angle_deg)


def _rotate_bitmap(bitmap: list[int], angle_deg: float) -> list[int]:
    """Rotate an 8×8 bitmap by angle_deg degrees (clockwise on screen).

    Produces a new 8×8 bitmap via nearest-neighbour sampling.
    """
    rad = math.radians(-angle_deg)   # negative = clockwise screen rotation
    cos_r = math.cos(rad)
    sin_r = math.sin(rad)
    cx = cy = 3.5   # centre of 8×8 grid

    result = [0] * 8
    for y in range(8):
        row = 0
        for x in range(8):
            # Source pixel via inverse rotation
            sx = (x - cx) * cos_r - (y - cy) * sin_r + cx
            sy = (x - cx) * sin_r + (y - cy) * cos_r + cy
            si = round(sy)
            sj = round(sx)
            if 0 <= si < 8 and 0 <= sj < 8:
                src_bit = (bitmap[si] >> (7 - sj)) & 1
            else:
                src_bit = 0
            row = (row << 1) | src_bit
        result[y] = row & 0xFF
    return result


# Pre-compute sprite tables
ENTERPRISE_SPRITES: list[list[int]] = [
    _make_ship_bitmap(i * 4) for i in range(_SPRITE_ANGLES)
]

KLINGON_SPRITES: list[list[int]] = [
    _make_klingon_bitmap(i * 4) for i in range(_SPRITE_ANGLES)
]


def get_enterprise_sprite(angle: int) -> list[int]:
    """Return the Enterprise sprite for the given 0-255 angle."""
    idx = (angle // 4) % _SPRITE_ANGLES
    return ENTERPRISE_SPRITES[idx]


def get_klingon_sprite(angle: int) -> list[int]:
    """Return the Klingon sprite for the given 0-255 angle."""
    idx = (angle // 4) % _SPRITE_ANGLES
    return KLINGON_SPRITES[idx]


# ---------------------------------------------------------------------------
# Explosion frames (8 frames, each 8×8)
# ---------------------------------------------------------------------------

def _make_explosion_frame(frame: int) -> list[int]:
    """Generate one explosion animation frame.

    Frame 0 = small spark; frame 7 = large scattered pixels.
    # TODO: transcribe exact data from PICTURES.ASM.
    """
    patterns = [
        [0x18, 0x18, 0x18, 0x18, 0x18, 0x18, 0x18, 0x18],  # 0 — tiny cross
        [0x24, 0x42, 0x18, 0x18, 0x18, 0x18, 0x42, 0x24],  # 1
        [0x42, 0x24, 0x18, 0x3C, 0x3C, 0x18, 0x24, 0x42],  # 2
        [0x81, 0x42, 0x3C, 0x7E, 0x7E, 0x3C, 0x42, 0x81],  # 3
        [0xC3, 0x66, 0x3C, 0xFF, 0xFF, 0x3C, 0x66, 0xC3],  # 4
        [0xE7, 0xDB, 0x66, 0xFF, 0xFF, 0x66, 0xDB, 0xE7],  # 5
        [0xFF, 0xDB, 0xBD, 0xFF, 0xFF, 0xBD, 0xDB, 0xFF],  # 6
        [0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF],  # 7 — solid block
    ]
    return patterns[frame % 8]


EXPLOSION_FRAME_DATA: list[list[int]] = [_make_explosion_frame(i) for i in range(8)]


def get_explosion_frame(n: int) -> list[int]:
    """Return explosion frame n (0=small, 7=large)."""
    return EXPLOSION_FRAME_DATA[n % 8]


# ---------------------------------------------------------------------------
# Planet frames (16 frames, each 16×16 pixels, represented as 16 ints)
# ---------------------------------------------------------------------------

def _make_planet_frame(frame: int) -> list[int]:
    """Generate one animated planet frame: 16 columns × 8 virtual rows.

    With Y_SCALE=2 each virtual row is drawn as 2 screen rows, so the bitmap
    renders as 16×16 screen pixels — a circle, not a tall oval.

    The circle equation in screen-pixel space is:
        dx² + (dy * Y_SCALE)² ≤ r²
    where dx = x - cx (pixels) and dy = y - cy (virtual rows).
    This is equivalent to: dx² + 4·dy² ≤ r².

    A crescent shadow moves left-to-right across 16 frames, simulating rotation.

    # TODO: transcribe exact data from PICTURES.ASM / PLANET.ASM.
    """
    rows = []
    cx = 7.5          # horizontal centre (between col 7 and 8)
    cy = 3.5          # vertical centre (between row 3 and 4)
    r = 7.5           # screen-pixel radius

    # Shadow circle: same shape, slightly smaller, offset horizontally
    # frame 0  → shadow far left  → right crescent lit
    # frame 8  → shadow centred   → thin ring lit
    # frame 15 → shadow far right → left crescent lit
    shadow_x = cx + (frame / 15.0 - 0.5) * (r * 1.2)
    shadow_r = r * 0.82

    for y in range(8):
        row = 0
        for x in range(16):
            dx = x - cx
            dy = y - cy
            in_planet = (dx * dx + 4 * dy * dy) <= r * r
            sdx = x - shadow_x
            in_shadow = (sdx * sdx + 4 * dy * dy) <= shadow_r * shadow_r
            if in_planet and not in_shadow:
                row |= (1 << (15 - x))
        rows.append(row)
    return rows


PLANET_FRAME_DATA: list[list[int]] = [_make_planet_frame(i) for i in range(16)]


def get_planet_frame(n: int) -> list[int]:
    """Return planet animation frame n (0..15)."""
    return PLANET_FRAME_DATA[n % 16]
