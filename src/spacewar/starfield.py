"""
512-star static starfield.

Stars are placed randomly within the active area (excluding the WRAP_FACTOR
border) in virtual 640×200 coordinates and remain fixed for the session.
"""

from __future__ import annotations
import random

from spacewar.constants import (
    VIRTUAL_W, VIRTUAL_H, WRAP_FACTOR, STAR_COUNT,
    Y_SCALE, WHITE,
)


class Starfield:
    """Holds the fixed star positions and draws them each frame."""

    def __init__(self, seed: int | None = None) -> None:
        rng = random.Random(seed)
        x_min = WRAP_FACTOR
        x_max = VIRTUAL_W - WRAP_FACTOR - 1
        y_min = WRAP_FACTOR
        y_max = VIRTUAL_H - WRAP_FACTOR - 1

        self._stars: list[tuple[int, int]] = [
            (rng.randint(x_min, x_max), rng.randint(y_min, y_max))
            for _ in range(STAR_COUNT)
        ]

    def draw(self, surface, neon: bool = False) -> None:
        """Blit all stars onto surface as single pixels."""
        colour = WHITE
        if neon:
            from spacewar.constants import NEON_STAR
            colour = NEON_STAR
        for x, y in self._stars:
            surface.set_at((x, y * Y_SCALE), colour)
