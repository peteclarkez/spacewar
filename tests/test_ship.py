"""
Tests for ship.py — kinematics, energy, damage, rotation, cooldowns.
"""

import pytest
from spacewar.ship import Ship
from spacewar.constants import (
    ENT_START_X, ENT_START_Y, ENT_START_A,
    KLN_START_X, KLN_START_Y, KLN_START_A,
    STARTING_SHIELDS, STARTING_ENERGY, MAX_ENERGY,
    DILITHIUM_TIME, IMPULSE_TIME, CLOAK_TIME, SWAP_TIME,
    MAX_VELOCITY, ROTATE_RATE,
    PHASER_FIRE_ENERGY, PHASER_DELAY,
    PHOTON_LAUNCH_ENERGY, HYPERSPACE_ENERGY,
    PLAYER_ENT, PLAYER_KLN,
    LOW_SHIELD_LIMIT,
)


class TestConstruction:
    def test_enterprise_defaults(self, ent_ship):
        assert ent_ship.player == PLAYER_ENT
        assert ent_ship.x      == ENT_START_X
        assert ent_ship.y      == ENT_START_Y
        assert ent_ship.angle  == ENT_START_A
        assert ent_ship.vx == ent_ship.vy == 0.0

    def test_klingon_defaults(self, kln_ship):
        assert kln_ship.player == PLAYER_KLN
        assert kln_ship.x     == KLN_START_X
        assert kln_ship.y     == KLN_START_Y
        assert kln_ship.angle == KLN_START_A

    def test_starting_energy(self, ent_ship):
        assert ent_ship.shields == STARTING_SHIELDS
        assert ent_ship.energy  == STARTING_ENERGY

    def test_starts_alive(self, ent_ship):
        assert ent_ship.alive
        assert not ent_ship.cloaked
        assert not ent_ship.dead


class TestReset:
    def test_reset_restores_position(self, ent_ship):
        ent_ship.x = 999
        ent_ship.y = 999
        ent_ship.reset()
        assert ent_ship.x == ENT_START_X
        assert ent_ship.y == ENT_START_Y

    def test_reset_restores_energy(self, ent_ship):
        ent_ship.shields = 5
        ent_ship.energy  = 10
        ent_ship.reset()
        assert ent_ship.shields == STARTING_SHIELDS
        assert ent_ship.energy  == STARTING_ENERGY

    def test_reset_preserves_score(self, ent_ship):
        ent_ship.score = 42
        ent_ship.reset()
        assert ent_ship.score == 42

    def test_reset_clears_dead_flag(self, ent_ship):
        ent_ship.dead  = True
        ent_ship.alive = False
        ent_ship.reset()
        assert ent_ship.alive
        assert not ent_ship.dead


class TestRotation:
    def test_rotate_left_decrements(self, ent_ship):
        ent_ship.angle = 10
        ent_ship.rotate_left()
        assert ent_ship.angle == 10 - ROTATE_RATE

    def test_rotate_right_increments(self, ent_ship):
        ent_ship.angle = 10
        ent_ship.rotate_right()
        assert ent_ship.angle == 10 + ROTATE_RATE

    def test_angle_wraps_positive(self, ent_ship):
        ent_ship.angle = 255
        ent_ship.rotate_right()
        assert ent_ship.angle == (255 + ROTATE_RATE) % 256

    def test_angle_wraps_negative(self, ent_ship):
        ent_ship.angle = 0
        ent_ship.rotate_left()
        assert ent_ship.angle == (256 - ROTATE_RATE) % 256


class TestThrust:
    def test_thrust_changes_velocity(self, ent_ship):
        """Thrust at angle 0 (East) should increase vx."""
        ent_ship.vx = 0.0
        ent_ship.apply_thrust()
        assert ent_ship.vx > 0

    def test_thrust_no_y_at_angle_0(self, ent_ship):
        ent_ship.vy = 0.0
        ent_ship.apply_thrust()
        assert abs(ent_ship.vy) < 1e-6

    def test_thrust_west_reduces_vx(self, ent_ship):
        ent_ship.angle = 128   # West
        ent_ship.vx = 0.0
        ent_ship.apply_thrust()
        assert ent_ship.vx < 0

    def test_thrust_does_not_exceed_cap(self, ent_ship):
        ent_ship.vx = float(MAX_VELOCITY)
        ent_ship.apply_thrust()
        assert ent_ship.vx <= MAX_VELOCITY

    def test_no_thrust_without_energy(self, ent_ship):
        ent_ship.energy = 0
        ent_ship.vx = 0.0
        ent_ship.apply_thrust()
        assert ent_ship.vx == 0.0

    def test_thrust_costs_energy_after_period(self, ent_ship):
        initial_e = ent_ship.energy
        for _ in range(IMPULSE_TIME):
            ent_ship.apply_thrust()
        assert ent_ship.energy == initial_e - 1


class TestCloak:
    def test_cloak_activates(self, ent_ship):
        ent_ship.apply_cloak()
        assert ent_ship.cloaked

    def test_deactivate_cloak(self, ent_ship):
        ent_ship.apply_cloak()
        ent_ship.deactivate_cloak()
        assert not ent_ship.cloaked

    def test_no_cloak_without_energy(self, ent_ship):
        ent_ship.energy = 0
        ent_ship.apply_cloak()
        assert not ent_ship.cloaked

    def test_cloak_costs_energy_after_period(self, ent_ship):
        initial_e = ent_ship.energy
        for _ in range(CLOAK_TIME):
            ent_ship.apply_cloak()
        assert ent_ship.energy == initial_e - 1


class TestEnergyRecharge:
    def test_energy_recharges(self, ent_ship):
        ent_ship.energy = 50
        for _ in range(DILITHIUM_TIME):
            ent_ship.tick_energy()
        assert ent_ship.energy == 51

    def test_energy_does_not_exceed_max(self, ent_ship):
        ent_ship.energy = MAX_ENERGY
        for _ in range(DILITHIUM_TIME * 2):
            ent_ship.tick_energy()
        assert ent_ship.energy == MAX_ENERGY


class TestEnergyTransfer:
    def test_shields_to_energy(self, ent_ship):
        ent_ship.shields = 20
        ent_ship.energy  = 50
        for _ in range(SWAP_TIME):
            ent_ship.shields_to_energy()
        assert ent_ship.shields == 19
        assert ent_ship.energy  == 51

    def test_energy_to_shields(self, ent_ship):
        ent_ship.shields = 20
        ent_ship.energy  = 50
        for _ in range(SWAP_TIME):
            ent_ship.energy_to_shields()
        assert ent_ship.shields == 21
        assert ent_ship.energy  == 49

    def test_no_transfer_from_empty_shields(self, ent_ship):
        ent_ship.shields = 0
        ent_ship.energy  = 50
        for _ in range(SWAP_TIME * 3):
            ent_ship.shields_to_energy()
        assert ent_ship.shields == 0   # Can't go below 0

    def test_no_transfer_from_empty_energy(self, ent_ship):
        ent_ship.shields = 20
        ent_ship.energy  = 0
        for _ in range(SWAP_TIME * 3):
            ent_ship.energy_to_shields()
        assert ent_ship.energy == 0


class TestDamage:
    def test_damage_reduces_shields(self, ent_ship):
        initial = ent_ship.shields
        dead = ent_ship.apply_damage(5)
        assert ent_ship.shields == initial - 5
        assert not dead

    def test_death_when_shields_negative(self, ent_ship):
        ent_ship.shields = 0
        dead = ent_ship.apply_damage(1)
        assert dead
        assert ent_ship.dead
        assert not ent_ship.alive

    def test_survive_at_zero_shields(self, ent_ship):
        ent_ship.shields = 1
        dead = ent_ship.apply_damage(1)
        # shields == 0 → still alive (death only on negative)
        assert not dead
        assert ent_ship.alive

    def test_large_damage_kills(self, ent_ship):
        ent_ship.shields = 5
        dead = ent_ship.apply_damage(10)
        assert dead


class TestPhaserCooldown:
    def test_can_fire_initially(self, ent_ship):
        assert ent_ship.can_fire_phaser()

    def test_cannot_fire_immediately_after(self, ent_ship):
        ent_ship.fire_phaser()
        assert not ent_ship.can_fire_phaser()

    def test_can_fire_after_cooldown(self, ent_ship):
        ent_ship.fire_phaser()
        for _ in range(PHASER_DELAY):
            ent_ship.tick_timers()
        assert ent_ship.can_fire_phaser()

    def test_phaser_costs_energy(self, ent_ship):
        initial = ent_ship.energy
        ent_ship.fire_phaser()
        assert ent_ship.energy == initial - PHASER_FIRE_ENERGY

    def test_no_fire_without_energy(self, ent_ship):
        ent_ship.energy = 0
        assert not ent_ship.can_fire_phaser()


class TestTorpedoDebounce:
    def test_first_press_fires(self, ent_ship):
        assert ent_ship.can_fire_torpedo(True)

    def test_held_key_does_not_refire(self, ent_ship):
        ent_ship.can_fire_torpedo(True)  # first press
        ent_ship.consume_torpedo_energy()
        assert not ent_ship.can_fire_torpedo(True)   # still held

    def test_refire_after_release(self, ent_ship):
        ent_ship.can_fire_torpedo(True)
        ent_ship.consume_torpedo_energy()
        ent_ship.can_fire_torpedo(False)  # release
        assert ent_ship.can_fire_torpedo(True)  # re-press


class TestHyperspaceCost:
    def test_hyperspace_costs_8(self, ent_ship):
        initial = ent_ship.energy
        assert ent_ship.can_hyperspace(True)
        ent_ship.consume_hyperspace_energy()
        assert ent_ship.energy == initial - HYPERSPACE_ENERGY

    def test_no_hyperspace_without_energy(self, ent_ship):
        ent_ship.energy = 7
        assert not ent_ship.can_hyperspace(True)


class TestShieldWarning:
    def test_warning_below_threshold(self, ent_ship):
        ent_ship.shields = LOW_SHIELD_LIMIT - 1
        assert ent_ship.shield_warning

    def test_no_warning_above_threshold(self, ent_ship):
        ent_ship.shields = LOW_SHIELD_LIMIT
        assert not ent_ship.shield_warning

    def test_warning_at_zero(self, ent_ship):
        ent_ship.shields = 0
        assert ent_ship.shield_warning


class TestMove:
    def test_moves_by_velocity(self, ent_ship):
        ent_ship.x, ent_ship.y = 200.0, 100.0
        ent_ship.vx, ent_ship.vy = 1.0, 1.0
        ent_ship.move(gravity_on=False)
        assert ent_ship.x == pytest.approx(201.0)
        assert ent_ship.y == pytest.approx(101.0)

    def test_gravity_changes_velocity(self, ent_ship):
        # Place ship far from planet centre
        ent_ship.x, ent_ship.y = 600.0, 100.0
        ent_ship.vx, ent_ship.vy = 0.0, 0.0
        ent_ship.move(gravity_on=True)
        # Should be pulled leftward toward planet at 319
        assert ent_ship.vx < 0
