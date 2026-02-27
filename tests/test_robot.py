"""
Tests for robot.py — left (defensive) and right (offensive) AI behaviour.
"""

import pytest
from unittest.mock import patch
from spacewar.robot import left_robot_tick, right_robot_tick, _in_phaser_range
from spacewar.ship import Ship
from spacewar.torpedo import TorpedoPool
from spacewar.constants import (
    PHASER_RANGE, PLAYER_ENT, PLAYER_KLN,
    STARTING_ENERGY, STARTING_SHIELDS,
)


@pytest.fixture()
def ent():
    return Ship.enterprise()


@pytest.fixture()
def kln():
    return Ship.klingon()


@pytest.fixture()
def ent_pool():
    return TorpedoPool(PLAYER_ENT)


@pytest.fixture()
def kln_pool():
    return TorpedoPool(PLAYER_KLN)


class TestPhaserRange:
    def test_in_range(self):
        assert _in_phaser_range(100, 50, 100 + PHASER_RANGE - 1, 50)

    def test_out_of_range_x(self):
        assert not _in_phaser_range(100, 50, 100 + PHASER_RANGE + 1, 50)

    def test_out_of_range_y(self):
        assert not _in_phaser_range(100, 50, 100, 50 + PHASER_RANGE + 1)

    def test_exactly_at_range(self):
        assert _in_phaser_range(100, 50, 100 + PHASER_RANGE, 50)


class TestLeftRobot:
    def test_left_robot_rotates_to_face_opponent(self, ent, kln, ent_pool):
        """Left robot aims at opponent."""
        kln.x, kln.y = 400.0, 50.0
        ent.x, ent.y = 100.0, 50.0
        left_robot_tick(ent, kln, ent_pool, False, 1)
        # Enterprise should now face East (positive X direction)
        from spacewar.trig import angle_between
        expected = angle_between(kln.x - ent.x, kln.y - ent.y)
        assert ent.angle == expected

    def test_left_robot_does_not_fire_torpedo(self, ent, kln, ent_pool):
        """Left robot only fires phasers, never torpedoes."""
        kln.x, kln.y = 400.0, 50.0
        ent.x, ent.y = 100.0, 50.0
        for tick in range(200):
            left_robot_tick(ent, kln, ent_pool, False, tick)
        # No torpedoes should have been fired
        active = ent_pool.active_torpedoes()
        assert len(active) == 0

    def test_left_robot_stops_when_no_energy(self, ent, kln, ent_pool):
        """Robot with zero energy should not attempt to thrust."""
        ent.energy = 0
        vx0, vy0 = ent.vx, ent.vy
        # Force impulse by making random always hit
        with patch("spacewar.robot.random") as mock_random:
            mock_random.randint.return_value = 0   # always triggers
            left_robot_tick(ent, kln, ent_pool, False, 1)
        # With no energy, thrust should not be applied
        assert ent.vx == vx0
        assert ent.vy == vy0

    def test_left_robot_fires_phaser_when_in_range(self, ent, kln, ent_pool):
        """Left robot fires phasers when opponent is within PHASER_RANGE."""
        ent.x, ent.y = 100.0, 50.0
        kln.x, kln.y = 150.0, 50.0   # within range
        assert _in_phaser_range(ent.x, ent.y, kln.x, kln.y)
        assert ent.can_fire_phaser()
        left_robot_tick(ent, kln, ent_pool, False, 1)
        # Phaser cooldown started → timer > 0
        assert ent.phaser_timer > 0


class TestRightRobot:
    def test_right_robot_always_faces_opponent(self, ent, kln, kln_pool):
        """Klingon robot rotates toward opponent every tick."""
        ent.x, ent.y = 100.0, 100.0
        kln.x, kln.y = 400.0, 100.0
        right_robot_tick(kln, ent, kln_pool, False, 1)
        from spacewar.trig import angle_between
        expected = angle_between(ent.x - kln.x, ent.y - kln.y)
        assert kln.angle == expected

    def test_right_robot_fires_torpedo_out_of_phaser_range(self, ent, kln, kln_pool):
        """Klingon robot fires torpedo when opponent is out of phaser range."""
        ent.x, ent.y = 100.0, 100.0
        kln.x, kln.y = 500.0, 100.0   # far apart
        assert not _in_phaser_range(kln.x, kln.y, ent.x, ent.y)
        # Force firing by making random always hit
        with patch("spacewar.robot.random") as mock_random:
            mock_random.randint.return_value = 0
            right_robot_tick(kln, ent, kln_pool, False, 1)
        # At least one torpedo should have been fired
        assert len(kln_pool.active_torpedoes()) >= 1

    def test_right_robot_fires_phaser_when_in_range(self, ent, kln, kln_pool):
        """Klingon robot fires phasers when opponent is within PHASER_RANGE."""
        ent.x, ent.y = 300.0, 50.0
        kln.x, kln.y = 340.0, 50.0   # close together
        assert _in_phaser_range(kln.x, kln.y, ent.x, ent.y)
        with patch("spacewar.robot.random") as mock_random:
            mock_random.randint.return_value = 0
            right_robot_tick(kln, ent, kln_pool, False, 1)
        assert kln.phaser_timer > 0     # phaser cooldown started
        assert len(kln_pool.active_torpedoes()) == 0   # no torpedo fired

    def test_right_robot_balances_energy(self, ent, kln, kln_pool):
        """Robot balances shields and energy toward equality."""
        kln.shields = 0
        kln.energy  = 100
        # Run many ticks to trigger swap
        for tick in range(100):
            right_robot_tick(kln, ent, kln_pool, False, tick)
        # Energy should have decreased (transferred to shields)
        assert kln.energy < 100

    def test_left_robot_balances_energy(self, ent, kln, ent_pool):
        """Left robot also balances S ↔ E."""
        ent.shields = 100   # artificially high
        ent.energy  = 10
        for tick in range(100):
            left_robot_tick(ent, kln, ent_pool, False, tick)
        assert ent.shields < 100
