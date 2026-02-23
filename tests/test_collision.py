"""Tests for collision.py — Manhattan distance collision detection."""

import pytest

from spacewar.init import GameObject, GameState, new_game_state
from spacewar.collision import (
    check_all_collisions, check_death,
    _in_range, _ship_ship_collision, _ship_torp_collision,
    _torp_torp_collision, _planet_collision,
)
from spacewar.constants import (
    ENT_OBJ, KLN_OBJ,
    ENT_TORP_START, ENT_TORP_END,
    KLN_TORP_START, KLN_TORP_END,
    EFLG_ACTIVE, EFLG_INACTIVE, EFLG_EXPLODING,
    SHIP_TO_SHIP_RANGE, SHIP_TO_TORP_RANGE, TORP_TO_TORP_RANGE,
    PHOTON_DAMAGE, PLANET_DAMAGE,
    PLANET_X, PLANET_Y, PLANET_RANGE, PLANET_BIT,
    BOUNCE_FACTOR, STARTING_SHIELDS,
)


def _active(x=100, y=50):
    obj = GameObject()
    obj.x = x
    obj.y = y
    obj.eflg = EFLG_ACTIVE
    obj.shields = STARTING_SHIELDS
    obj.exps = 0
    return obj


class TestInRange:
    def test_well_within(self):
        a = _active(100, 50)
        b = _active(100 + SHIP_TO_SHIP_RANGE - 2, 50)
        assert _in_range(a, b, SHIP_TO_SHIP_RANGE)

    def test_exactly_at_boundary_is_outside(self):
        """abs(dx) < range → dx == range is NOT a hit."""
        a = _active(100, 50)
        b = _active(100 + SHIP_TO_SHIP_RANGE, 50)
        assert not _in_range(a, b, SHIP_TO_SHIP_RANGE)

    def test_one_axis_out_of_range(self):
        """Both axes must be within range."""
        a = _active(100, 50)
        b = _active(100 + SHIP_TO_SHIP_RANGE - 1, 50 + SHIP_TO_SHIP_RANGE)
        assert not _in_range(a, b, SHIP_TO_SHIP_RANGE)

    def test_same_position(self):
        a = _active(100, 50)
        b = _active(100, 50)
        assert _in_range(a, b, 1)

    def test_negative_offset(self):
        a = _active(100, 50)
        b = _active(100 - SHIP_TO_SHIP_RANGE + 1, 50)
        assert _in_range(a, b, SHIP_TO_SHIP_RANGE)


class TestShipShipCollision:
    def _state_with_ships(self, ent_x, ent_y, kln_x, kln_y,
                          ent_vx=4, ent_vy=0, kln_vx=-2, kln_vy=3):
        state = new_game_state()
        ent = state.objects[ENT_OBJ]
        kln = state.objects[KLN_OBJ]
        ent.x, ent.y = ent_x, ent_y
        kln.x, kln.y = kln_x, kln_y
        ent.vx, ent.vy = ent_vx, ent_vy
        kln.vx, kln.vy = kln_vx, kln_vy
        ent.eflg = kln.eflg = EFLG_ACTIVE
        return state

    def test_no_collision_far_apart(self):
        state = self._state_with_ships(100, 50, 200, 50)
        ent_vx = state.objects[ENT_OBJ].vx
        _ship_ship_collision(state)
        assert state.objects[ENT_OBJ].vx == ent_vx   # unchanged

    def test_collision_swaps_velocities(self):
        """On collision, each ship gets half the other's velocity."""
        state = self._state_with_ships(100, 50, 102, 50, ent_vx=4, kln_vx=-2)
        _ship_ship_collision(state)
        ent = state.objects[ENT_OBJ]
        kln = state.objects[KLN_OBJ]
        # Each gets half the other's original velocity
        assert ent.vx == (-2) >> 1   # -1
        assert kln.vx == 4 >> 1      # 2

    def test_collision_no_shield_damage(self):
        """Ship-ship collision does NOT damage shields."""
        state = self._state_with_ships(100, 50, 102, 50)
        shields_before = state.objects[ENT_OBJ].shields
        _ship_ship_collision(state)
        assert state.objects[ENT_OBJ].shields == shields_before

    def test_ships_pushed_apart(self):
        """Ships are separated by BOUNCE_FACTOR after collision."""
        state = self._state_with_ships(100, 50, 100, 50)   # same position
        _ship_ship_collision(state)
        ent = state.objects[ENT_OBJ]
        kln = state.objects[KLN_OBJ]
        # They should now be apart (exact direction depends on dx=0 → dy used)
        assert ent.y != kln.y or ent.x != kln.x


class TestShipTorpCollision:
    def test_torpedo_hit_damages_ship(self):
        state = new_game_state()
        ship = state.objects[ENT_OBJ]
        ship.x, ship.y = 100, 50
        ship.shields = STARTING_SHIELDS

        torp = state.objects[KLN_TORP_START]
        torp.x, torp.y = 101, 50   # within range
        torp.eflg = EFLG_ACTIVE

        torps = [(KLN_TORP_START, torp)]
        _ship_torp_collision(ship, torps)

        assert ship.shields == STARTING_SHIELDS - PHOTON_DAMAGE
        assert torp.eflg == EFLG_EXPLODING

    def test_torpedo_miss_no_damage(self):
        state = new_game_state()
        ship = state.objects[ENT_OBJ]
        ship.x, ship.y = 100, 50
        ship.shields = STARTING_SHIELDS

        torp = state.objects[KLN_TORP_START]
        torp.x, torp.y = 200, 50   # far away
        torp.eflg = EFLG_ACTIVE

        torps = [(KLN_TORP_START, torp)]
        _ship_torp_collision(ship, torps)

        assert ship.shields == STARTING_SHIELDS
        assert torp.eflg == EFLG_ACTIVE

    def test_self_hit_possible(self):
        """Ships can be hit by their own torpedoes."""
        state = new_game_state()
        ship = state.objects[ENT_OBJ]
        ship.x, ship.y = 100, 50
        ship.shields = STARTING_SHIELDS

        ent_torp = state.objects[ENT_TORP_START]
        ent_torp.x, ent_torp.y = 101, 50
        ent_torp.eflg = EFLG_ACTIVE

        own_torps = [(ENT_TORP_START, ent_torp)]
        _ship_torp_collision(ship, own_torps)

        assert ship.shields == STARTING_SHIELDS - PHOTON_DAMAGE

    def test_inactive_torpedo_not_collide(self):
        state = new_game_state()
        ship = state.objects[ENT_OBJ]
        ship.x, ship.y = 100, 50
        ship.shields = STARTING_SHIELDS

        torp = state.objects[KLN_TORP_START]
        torp.x, torp.y = 101, 50
        torp.eflg = EFLG_INACTIVE

        torps = [(KLN_TORP_START, torp)]
        _ship_torp_collision(ship, torps)

        assert ship.shields == STARTING_SHIELDS


class TestTorpTorpCollision:
    def test_collision_both_explode(self):
        state = new_game_state()
        et = state.objects[ENT_TORP_START]
        kt = state.objects[KLN_TORP_START]

        et.x, et.y = 100, 50
        et.eflg = EFLG_ACTIVE
        kt.x, kt.y = 101, 50
        kt.eflg = EFLG_ACTIVE

        _torp_torp_collision(
            [(ENT_TORP_START, et)],
            [(KLN_TORP_START, kt)],
        )

        assert et.eflg == EFLG_EXPLODING
        assert kt.eflg == EFLG_EXPLODING

    def test_no_collision_far_apart(self):
        state = new_game_state()
        et = state.objects[ENT_TORP_START]
        kt = state.objects[KLN_TORP_START]

        et.x, et.y = 100, 50
        et.eflg = EFLG_ACTIVE
        kt.x, kt.y = 200, 50
        kt.eflg = EFLG_ACTIVE

        _torp_torp_collision(
            [(ENT_TORP_START, et)],
            [(KLN_TORP_START, kt)],
        )

        assert et.eflg == EFLG_ACTIVE
        assert kt.eflg == EFLG_ACTIVE


class TestPlanetCollision:
    def test_ship_in_range_loses_shields(self):
        state = new_game_state()
        state.planet_enable = PLANET_BIT
        ship = state.objects[ENT_OBJ]
        ship.x = PLANET_X + 1
        ship.y = PLANET_Y
        ship.shields = STARTING_SHIELDS

        _planet_collision(state)
        assert ship.shields == STARTING_SHIELDS - PLANET_DAMAGE

    def test_torpedo_in_range_explodes(self):
        state = new_game_state()
        state.planet_enable = PLANET_BIT
        torp = state.objects[ENT_TORP_START]
        torp.x = PLANET_X + 1
        torp.y = PLANET_Y
        torp.eflg = EFLG_ACTIVE

        _planet_collision(state)
        assert torp.eflg == EFLG_EXPLODING

    def test_planet_disabled_no_collision(self):
        state = new_game_state()
        state.planet_enable = 0   # planet off
        ship = state.objects[ENT_OBJ]
        ship.x = PLANET_X
        ship.y = PLANET_Y
        ship.shields = STARTING_SHIELDS

        _planet_collision(state)
        assert ship.shields == STARTING_SHIELDS

    def test_ship_far_from_planet_no_damage(self):
        state = new_game_state()
        state.planet_enable = PLANET_BIT
        ship = state.objects[ENT_OBJ]
        ship.x = PLANET_X + PLANET_RANGE + 10
        ship.y = PLANET_Y
        ship.shields = STARTING_SHIELDS

        _planet_collision(state)
        assert ship.shields == STARTING_SHIELDS


class TestCheckDeath:
    def test_negative_shields_dead(self):
        state = new_game_state()
        state.objects[ENT_OBJ].shields = -1
        result = check_death(state)
        assert result == ENT_OBJ

    def test_zero_shields_alive(self):
        """Death at shields < 0, NOT at 0."""
        state = new_game_state()
        state.objects[ENT_OBJ].shields = 0
        result = check_death(state)
        assert result == -1

    def test_positive_shields_alive(self):
        state = new_game_state()
        state.objects[ENT_OBJ].shields = 5
        result = check_death(state)
        assert result == -1

    def test_klingon_death(self):
        state = new_game_state()
        state.objects[KLN_OBJ].shields = -1
        result = check_death(state)
        assert result == KLN_OBJ

    def test_no_death(self):
        state = new_game_state()
        result = check_death(state)
        assert result == -1
