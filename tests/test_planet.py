"""
Tests for planet.py — collision detection and animation.
"""

import pytest
from spacewar.planet import Planet
from spacewar.constants import (
    PLANET_X, PLANET_Y, PLANET_RANGE, PLANET_TIME, PLANET_FRAMES,
)


class TestPlanetContains:
    def test_centre_is_inside(self):
        p = Planet()
        assert p.contains(PLANET_X, PLANET_Y)

    def test_edge_is_inside(self):
        p = Planet()
        assert p.contains(PLANET_X + PLANET_RANGE, PLANET_Y)

    def test_outside(self):
        p = Planet()
        assert not p.contains(PLANET_X + PLANET_RANGE + 1, PLANET_Y)

    def test_far_away(self):
        p = Planet()
        assert not p.contains(0.0, 0.0)

    def test_diagonal(self):
        import math
        p = Planet()
        # Exactly on the boundary diagonally
        d = PLANET_RANGE / math.sqrt(2)
        assert p.contains(PLANET_X + d, PLANET_Y + d)

    def test_just_outside_diagonal(self):
        import math
        p = Planet()
        d = (PLANET_RANGE + 1) / math.sqrt(2)
        assert not p.contains(PLANET_X + d, PLANET_Y + d)


class TestPlanetAnimation:
    def test_initial_frame(self):
        p = Planet()
        assert p.frame == 0

    def test_frame_advances(self):
        p = Planet()
        for _ in range(PLANET_TIME):
            p.update()
        assert p.frame == 1

    def test_frame_wraps(self):
        p = Planet()
        for _ in range(PLANET_TIME * PLANET_FRAMES):
            p.update()
        assert p.frame == 0

    def test_16_frames(self):
        assert PLANET_FRAMES == 16

    def test_reset_clears_frame(self):
        p = Planet()
        for _ in range(PLANET_TIME * 3):
            p.update()
        p.reset()
        assert p.frame == 0
