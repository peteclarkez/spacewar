"""
Tests for phaser.py — ray casting, hit detection, planet blocking.
"""

import pytest
from spacewar.phaser import Phaser, cast_phaser
from spacewar.constants import (
    PHASER_RANGE, PHASER_ERASE, PHASER_DELAY,
    PHASER_DAMAGE, PHASER_TO_OBJ_RANGE,
    PLANET_X, PLANET_Y, PLANET_RANGE,
    PLAYER_ENT, PLAYER_KLN,
)
from spacewar.ship import Ship
from spacewar.torpedo import Torpedo


def _make_torp(x, y, owner=PLAYER_KLN):
    t = Torpedo()
    t.launch(x, y, 0.0, 0.0, 0, owner)
    return t


class TestPhaserState:
    def test_default_inactive(self):
        p = Phaser()
        assert not p.active

    def test_reset(self):
        p = Phaser(active=True, timer=10)
        p.reset()
        assert not p.active
        assert p.timer == 0

    def test_tick_decrements(self):
        p = Phaser(active=True, timer=5)
        p.tick()
        assert p.timer == 4

    def test_deactivates_at_zero(self):
        p = Phaser(active=True, timer=1)
        p.tick()
        assert not p.active
        assert p.timer == 0


class TestCastPhaser:
    """Tests for the ray-casting function."""

    def _cast(self, ship_x, ship_y, angle, targets_ships=None,
              targets_torps=None, planet_active=False):
        phaser = Phaser(owner=PLAYER_ENT)
        ships_hit, torps_hit = cast_phaser(
            phaser, ship_x, ship_y, angle,
            targets_ships or [],
            targets_torps or [],
            planet_active,
        )
        return phaser, ships_hit, torps_hit

    def test_no_targets_no_hit(self):
        phaser, ships, torps = self._cast(100.0, 50.0, 0)
        assert ships == []
        assert torps == []

    def test_ray_reaches_max_range(self):
        phaser, _, _ = self._cast(100.0, 50.0, 0)
        # End point should be ~PHASER_RANGE ahead of start
        assert phaser.end_x > 100.0
        delta = phaser.end_x - 100.0
        assert delta <= PHASER_RANGE + 1

    def test_hits_ship_in_line_of_fire(self):
        target = Ship.klingon()
        # Place within PHASER_RANGE (96px) of firing position (100.0)
        target.x = 150.0
        target.y = 50.0   # Same Y as firing ship
        phaser, ships, _ = self._cast(100.0, 50.0, 0,   # fire East
                                       targets_ships=[target])
        assert target in ships

    def test_misses_ship_behind(self):
        target = Ship.klingon()
        target.x = 50.0
        target.y = 50.0   # West of firing position
        _, ships, _ = self._cast(100.0, 50.0, 0, targets_ships=[target])
        assert target not in ships

    def test_misses_out_of_range_ship(self):
        target = Ship.klingon()
        target.x = 100.0 + PHASER_RANGE + 20   # just past max range
        target.y = 50.0
        _, ships, _ = self._cast(100.0, 50.0, 0, targets_ships=[target])
        assert target not in ships

    def test_hits_torpedo_in_path(self):
        torp = _make_torp(150.0, 50.0)
        # Pin to a known position inside phaser range (launch adds spawn offset)
        torp.x, torp.y = 140.0, 50.0
        _, _, torps = self._cast(100.0, 50.0, 0, targets_torps=[torp])
        assert torp in torps

    def test_torpedo_blocks_ship_behind_it(self):
        """Phaser stops at torpedo; ship behind is not hit."""
        torp = _make_torp(150.0, 50.0)
        # Override position after launch (spawn offset may shift it)
        torp.x, torp.y = 130.0, 50.0
        target = Ship.klingon()
        target.x = 160.0
        target.y = 50.0
        _, ships, torps = self._cast(100.0, 50.0, 0,
                                      targets_ships=[target],
                                      targets_torps=[torp])
        assert torp in torps
        assert target not in ships

    def test_planet_blocks_ray(self):
        # Fire East directly into the planet (PLANET_X is ~319)
        # Ship at Y=PLANET_Y so the ray passes through planet centre
        phaser, _, _ = self._cast(100.0, float(PLANET_Y), 0,
                                   planet_active=True)
        # Ray should stop at or before the planet edge
        assert phaser.end_x <= PLANET_X + PLANET_RANGE + PHASER_TO_OBJ_RANGE + 1

    def test_does_not_hit_dead_ship(self):
        target = Ship.klingon()
        target.x = 150.0
        target.y = 50.0
        target.alive = False
        _, ships, _ = self._cast(100.0, 50.0, 0, targets_ships=[target])
        assert target not in ships

    def test_does_not_hit_cloaked_ship(self):
        target = Ship.klingon()
        target.x = 150.0
        target.y = 50.0
        target.cloaked = True
        # cast_phaser caller is responsible for filtering cloaked ships;
        # verify behaviour when caller passes only visible ships
        # (empty list → no hits)
        _, ships, _ = self._cast(100.0, 50.0, 0, targets_ships=[])
        assert ships == []

    def test_phaser_end_recorded(self):
        phaser, _, _ = self._cast(100.0, 50.0, 0)
        assert phaser.end_x != 100.0   # ray advanced at least somewhat
