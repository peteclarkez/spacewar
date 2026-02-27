"""
256-unit angle system with pre-computed sine/cosine lookup tables.

A full rotation = 256 angle units.
Table values are 15-bit integers in range [-32767, +32767]  (32767 ≈ 1.0).

Angle 0   → East  (positive X)
Angle 64  → South (positive Y, screen downward)
Angle 128 → West  (negative X)
Angle 192 → North (negative Y, screen upward)
"""

from __future__ import annotations
import math

# ── Build tables once at import time ─────────────────────────────────────────

_TWO_PI = 2.0 * math.pi
_SCALE  = 32767          # ≈ 1.0 in our fixed-point representation

SIN_TABLE: list[int] = [
    round(math.sin(i * _TWO_PI / 256) * _SCALE) for i in range(256)
]

COS_TABLE: list[int] = [
    round(math.cos(i * _TWO_PI / 256) * _SCALE) for i in range(256)
]

# Arctangent lookup: maps (dy, dx) pair to an angle in [0, 255].
# Populated lazily; use angle_between() instead of direct access.

def sin_fp(angle: int) -> int:
    """Return sin(angle) in fixed-point [-32767, 32767]."""
    return SIN_TABLE[angle & 0xFF]


def cos_fp(angle: int) -> int:
    """Return cos(angle) in fixed-point [-32767, 32767]."""
    return COS_TABLE[angle & 0xFF]


def angle_between(dx: float, dy: float) -> int:
    """
    Return the 256-unit angle from origin toward (dx, dy).
    dy is positive downward (screen coords).
    Returns 0 if dx == dy == 0.
    """
    if dx == 0 and dy == 0:
        return 0
    rad = math.atan2(dy, dx)          # atan2 in standard math coords
    unit = round(rad / _TWO_PI * 256) % 256
    return unit


def fp_to_float(fp_value: int) -> float:
    """Convert a fixed-point trig table value to a float in [-1.0, 1.0]."""
    return fp_value / _SCALE


def thrust_components(angle: int, accel_scale: int = 3) -> tuple[float, float]:
    """
    Return (ax, ay) thrust acceleration for one tick at the given angle.

    The original uses: velocity_dword += trig_value >> ACCEL_SCALE
    In our float model: v += (trig >> accel_scale) / FRAC  (FRAC = 65536)
    """
    from spacewar.constants import FRAC
    ax = (cos_fp(angle) >> accel_scale) / FRAC
    ay = (sin_fp(angle) >> accel_scale) / FRAC
    return ax, ay


def torpedo_velocity(angle: int, fire_scale: int = 2) -> tuple[float, float]:
    """
    Return the torpedo velocity components added to the ship's velocity.

    Original: torp_vel += (trig >> (15 - FIRE_SCALE))  in fixed-point.
    Simplified: vel_component = cos/sin(angle) * (1 << FIRE_SCALE) / _SCALE
    Effective multiplier ≈ 4× compared to MAX_VELOCITY.
    """
    # FIRE_SCALE=2 → left-shift by 2 → ×4 relative to the unit-normalised value.
    # The trig value is in fixed-point with _SCALE ≈ 2^15.
    # We want velocity in px/tick units (max ~MAX_VELOCITY = 8).
    # cos(0) = 32767; after <<2 = 131068; divide by 65536 (FRAC) ≈ 2.0
    # So a torpedo fired forward gains ~2 px/tick above ship velocity.
    from spacewar.constants import FRAC
    scale = 1 << fire_scale          # 4
    vx = (cos_fp(angle) * scale) / FRAC
    vy = (sin_fp(angle) * scale) / FRAC
    return vx, vy


def spawn_offset(angle: int, shift: int = 11) -> tuple[float, float]:
    """
    Torpedo spawn offset from ship centre: cos/sin(angle) >> shift.
    shift=11 → max offset ≈ 32767 / 2048 ≈ 16 virtual pixels.
    """
    ox = cos_fp(angle) >> shift
    oy = sin_fp(angle) >> shift
    return float(ox), float(oy)
