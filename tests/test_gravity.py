"""Tests for gravity.py — bowl gravity toward planet centre."""

import pytest

from spacewar.init import GameObject, GameState, new_game_state
from spacewar.gravity import apply_gravity, update_gravity_all
from spacewar.constants import (
    PLANET_X, PLANET_Y, GRAVITY_BIT, PLANET_BIT,
    ENT_OBJ, EFLG_ACTIVE, EFLG_INACTIVE,
)


def _obj_at(x: int, y: int) -> GameObject:
    """Create an active object at (x, y) with zero velocity."""
    obj = GameObject()
    obj.x = x
    obj.y = y
    obj.eflg = EFLG_ACTIVE
    return obj


class TestApplyGravity:
    def test_at_planet_centre_no_acceleration(self):
        """Object at planet centre → zero acceleration applied."""
        obj = _obj_at(PLANET_X, PLANET_Y)
        apply_gravity(obj)
        assert obj.vx_frac == 0
        assert obj.vy_frac == 0
        assert obj.vx == 0
        assert obj.vy == 0

    def test_right_of_planet(self):
        """Object 10px right → accel_x = -(10 * 8) = -80 added to vx_frac."""
        obj = _obj_at(PLANET_X + 10, PLANET_Y)
        apply_gravity(obj)
        # dx = 10, accel_x = -(10 << 3) = -80
        # Since -80 added to vx_frac=0: new_vx_frac = -80 (negative)
        # carry = -80 >> 16 = -1, vx_frac = (-80) & 0xFFFF = 65456
        expected_carry = (-80) >> 16   # = -1
        expected_frac = (-80) & 0xFFFF  # = 65456
        assert obj.vx == expected_carry
        assert obj.vx_frac == expected_frac

    def test_below_planet(self):
        """Object 10px below → accel_y = -(10 * 8) = -80."""
        obj = _obj_at(PLANET_X, PLANET_Y + 10)
        apply_gravity(obj)
        expected_carry = (-80) >> 16
        expected_frac = (-80) & 0xFFFF
        assert obj.vy == expected_carry
        assert obj.vy_frac == expected_frac
        assert obj.vx == 0
        assert obj.vx_frac == 0

    def test_accumulates_over_ticks(self):
        """Multiple ticks accumulate acceleration."""
        obj = _obj_at(PLANET_X + 5, PLANET_Y)
        # accel_x = -(5 * 8) = -40 per tick
        for _ in range(10):
            apply_gravity(obj)
        # After 10 ticks, total fractional change = -400
        # -400 in 16-bit: carry = -400 >> 16 = -1 (when frac underflows)
        total = -40 * 10   # = -400
        expected_carry = total >> 16
        expected_frac = total & 0xFFFF
        assert obj.vx == expected_carry
        assert obj.vx_frac == expected_frac

    def test_left_of_planet_positive_acceleration(self):
        """Object left of planet → positive x acceleration (pulled right)."""
        obj = _obj_at(PLANET_X - 10, PLANET_Y)
        apply_gravity(obj)
        # dx = -10, accel_x = -(-10 * 8) = 80
        expected_carry = 80 >> 16  # = 0
        expected_frac = 80 & 0xFFFF  # = 80
        assert obj.vx == expected_carry
        assert obj.vx_frac == expected_frac


class TestUpdateGravityAll:
    def test_gravity_disabled_no_effect(self):
        """Gravity bit not set → no acceleration applied."""
        state = new_game_state()
        state.planet_enable = 0   # neither bit set
        obj = state.objects[ENT_OBJ]
        obj.x = PLANET_X + 10
        obj.y = PLANET_Y
        obj.eflg = EFLG_ACTIVE
        vx_before = obj.vx_frac

        update_gravity_all(state)
        assert obj.vx_frac == vx_before

    def test_gravity_enabled_all_active(self):
        """All active objects receive gravity when GRAVITY_BIT is set."""
        state = new_game_state()
        state.planet_enable = GRAVITY_BIT
        # Move ENT_OBJ right of planet
        state.objects[ENT_OBJ].x = PLANET_X + 20
        state.objects[ENT_OBJ].y = PLANET_Y
        state.objects[ENT_OBJ].eflg = EFLG_ACTIVE

        update_gravity_all(state)
        # accel = -(20 * 8) = -160 added to vx_frac
        expected_frac = (-160) & 0xFFFF
        assert state.objects[ENT_OBJ].vx_frac == expected_frac

    def test_inactive_objects_not_affected(self):
        """Inactive objects are skipped by gravity."""
        state = new_game_state()
        state.planet_enable = GRAVITY_BIT
        torp = state.objects[1]   # Enterprise torpedo slot 1
        torp.eflg = EFLG_INACTIVE
        torp.x = PLANET_X + 50
        torp.y = PLANET_Y

        update_gravity_all(state)
        assert torp.vx_frac == 0
        assert torp.vy_frac == 0

    def test_planet_bit_without_gravity_bit(self):
        """PLANET_BIT alone does not enable gravity."""
        state = new_game_state()
        state.planet_enable = PLANET_BIT   # visible but no gravity
        obj = state.objects[ENT_OBJ]
        obj.x = PLANET_X + 10
        obj.eflg = EFLG_ACTIVE
        vx_frac_before = obj.vx_frac

        update_gravity_all(state)
        assert obj.vx_frac == vx_frac_before
