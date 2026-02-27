"""
Animated planet — 16-frame scanline animation, collision hazard, rendering.

The planet sprite cycles through 16 states every PLANET_TIME ticks.
Collision is a circular region of radius PLANET_RANGE in virtual coords.
"""

from __future__ import annotations

from spacewar.constants import (
    PLANET_X, PLANET_Y, PLANET_RANGE, PLANET_TIME, PLANET_FRAMES,
    PLANET_DRAW_W, PLANET_DRAW_H, PLANET_DAMAGE,
    Y_SCALE, WHITE,
)
from spacewar.physics import distance


class Planet:
    """Manages planet animation state and provides drawing helpers."""

    def __init__(self) -> None:
        self.frame: int = 0        # current animation frame 0-15
        self._tick:  int = 0       # internal tick counter

    def reset(self) -> None:
        self.frame = 0
        self._tick  = 0

    def update(self) -> None:
        """Advance animation one tick."""
        self._tick += 1
        if self._tick >= PLANET_TIME:
            self._tick = 0
            self.frame = (self.frame + 1) % PLANET_FRAMES

    def contains(self, x: float, y: float) -> bool:
        """Return True if virtual-space point (x, y) is inside the planet."""
        return distance(x, y, PLANET_X, PLANET_Y) <= PLANET_RANGE

    def draw(self, surface, neon: bool = False,
             cx: int = PLANET_X, cy: int = PLANET_Y,
             scale_factor: float = 1.0) -> None:
        """
        Draw the planet centred at virtual coords (cx, cy).
        scale_factor < 1 is used for the attract-mode thumbnail.
        """
        from spacewar import sprites as SP

        planet_surf = SP.get_planet_surface()
        if planet_surf is None:
            return

        if scale_factor != 1.0:
            import pygame
            w = int(PLANET_DRAW_W * scale_factor)
            h = int(PLANET_DRAW_H * scale_factor)
            planet_surf = pygame.transform.scale(planet_surf, (w, h))
        else:
            w, h = PLANET_DRAW_W, PLANET_DRAW_H

        sx = int(cx) - w // 2
        sy = int(cy) * Y_SCALE - h // 2

        # Tint for neon mode (planet is colour-shifted, no glow halo per spec)
        if neon:
            from spacewar.constants import NEON_PLANET
            import pygame
            tinted = planet_surf.copy()
            tinted.fill(NEON_PLANET, special_flags=pygame.BLEND_MULT)
            surface.blit(tinted, (sx, sy))
        else:
            surface.blit(planet_surf, (sx, sy))

        # Draw animated scanlines inside the planet body
        self._draw_scanlines(surface, cx, cy, scale_factor, neon)

    def _draw_scanlines(self, surface, cx: int, cy: int,
                        scale_factor: float, neon: bool) -> None:
        """
        Draw horizontal scanlines inside the planet.  The scanline positions
        shift each animation frame to give the impression of rotation.
        """
        import pygame
        colour = WHITE
        if neon:
            from spacewar.constants import NEON_PLANET
            colour = NEON_PLANET

        # Scanlines cover the inner body of the planet (virtual radius ~12 px)
        inner_r = int(PLANET_RANGE * 0.75 * scale_factor)
        screen_cx = int(cx)
        screen_cy = int(cy) * Y_SCALE

        # 4 scanlines cycle vertically through the planet body based on frame
        for i in range(4):
            # Offset moves down by 1 virtual pixel per frame
            row_offset = (self.frame + i * 4) % (inner_r * 2)
            sy = screen_cy - inner_r * Y_SCALE + row_offset * Y_SCALE

            # Chord width at this row
            dy_v = (row_offset - inner_r)
            if abs(dy_v) >= inner_r:
                continue
            chord_half = int(math.sqrt(inner_r ** 2 - dy_v ** 2) * scale_factor)
            if chord_half < 1:
                continue
            pygame.draw.line(surface, colour,
                             (screen_cx - chord_half, sy),
                             (screen_cx + chord_half, sy), 1)


import math   # needed for _draw_scanlines — placed at end to avoid circular import
