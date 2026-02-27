"""stars.py — PRNG and starfield generation.

Public API
----------
seed_random(state)                        — seed PRNG from system time
random_next(state) -> int                 — 0..65535
random_x(state) -> int                    — within safe x bounds
random_y(state) -> int                    — within safe y bounds
generate_stars(state) -> list[tuple]      — 512 (x,y) star positions
"""

import time

from .constants import (
    VIRTUAL_W, VIRTUAL_H, WRAP_FACTOR,
)

# Star count (CGA mode)
STAR_COUNT: int = 512


# ---------------------------------------------------------------------------
# PRNG — 6-byte shift-feedback pseudorandom number generator
# ---------------------------------------------------------------------------
# The rng_state is a list[int] of 6 bytes (indices 0-5).


def seed_random(rng: list[int]) -> None:
    """Seed the 6-byte PRNG from the system clock."""
    t = int(time.monotonic() * 1000) & 0xFFFFFFFF
    rng[1] = t & 0xFF
    rng[2] = (t >> 8) & 0xFF
    rng[3] = (t >> 16) & 0xFF
    rng[4] = (t >> 24) & 0xFF
    rng[0] = 0
    rng[5] = 0xA5  # arbitrary non-zero seed


def random_next(rng: list[int]) -> int:
    """Generate next pseudo-random number in range 0..65535.

    Returns (rng[2] << 8) | rng[0] after the shift.
    """
    # stc → carry = 1
    carry = 1
    # al = RND[1] + RND[4] + RND[5] + carry, keep only low byte
    total = rng[1] + rng[4] + rng[5] + carry
    new_byte = total & 0xFF

    # Shift RND[0..4] → RND[1..5]  (di loops 4 down to 0)
    rng[5] = rng[4]
    rng[4] = rng[3]
    rng[3] = rng[2]
    rng[2] = rng[1]
    rng[1] = rng[0]

    # Store new byte at RND[0]
    rng[0] = new_byte

    # Return ax = (RND[2] << 8) | RND[0]  (after shift, old RND[1] is now RND[2])
    return (rng[2] << 8) | rng[0]


def random_x(rng: list[int]) -> int:
    """Return a random x in [WRAP_FACTOR, VIRTUAL_W - WRAP_FACTOR)."""
    while True:
        val = random_next(rng) & (1024 - 1)  # get under 1024
        if WRAP_FACTOR <= val < VIRTUAL_W - WRAP_FACTOR:
            return val


def random_y(rng: list[int]) -> int:
    """Return a random y in [WRAP_FACTOR, VIRTUAL_H - WRAP_FACTOR)."""
    while True:
        val = random_next(rng) & (512 - 1)  # get under 512
        if WRAP_FACTOR <= val < VIRTUAL_H - WRAP_FACTOR:
            return val


def generate_stars(rng: list[int]) -> list[tuple[int, int]]:
    """Generate STAR_COUNT star positions using the PRNG.

    Returns list of (x, y) virtual coordinates.
    """
    positions: list[tuple[int, int]] = []
    for _ in range(STAR_COUNT):
        x = random_x(rng)
        y = random_y(rng)
        positions.append((x, y))
    return positions
