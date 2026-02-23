"""Tests for physics.py — position integration, energy, timing."""

import pytest

from spacewar.init import GameObject, GameState, new_game_state
from spacewar.physics import (
    run_physics_tick, update_position, apply_thrust,
    _tick_energy_recharge, _tick_torpedo_energy, _tick_phaser_states,
)
from spacewar.constants import (
    VIRTUAL_W, VIRTUAL_H, WRAP_FACTOR,
    MAX_X_VEL, MAX_Y_VEL,
    ACCEL_SCALE, THRUST_BIT,
    EFLG_ACTIVE, EFLG_INACTIVE, EFLG_EXPLODING,
    ENT_OBJ, KLN_OBJ,
    ENT_TORP_START, ENT_TORP_END,
    PHASER_IDLE, PHASER_ERASE,
    STARTING_ENERGY,
    PHOTON_ENERGY, PHOTON_TIME, DILITHIUM_TIME,
)


def _active_obj(x=100, y=50, vx=0, vy=0):
    obj = GameObject()
    obj.x = x
    obj.y = y
    obj.vx = vx
    obj.vy = vy
    obj.eflg = EFLG_ACTIVE
    return obj


class TestUpdatePosition:
    def test_simple_move(self):
        """vx=1 → x advances by 1 after one update."""
        obj = _active_obj(x=100, vx=1)
        update_position(obj)
        assert obj.x == 101

    def test_negative_velocity(self):
        """vx=-1 → x decreases by 1."""
        obj = _active_obj(x=100, vx=-1)
        update_position(obj)
        assert obj.x == 99

    def test_fractional_carry(self):
        """Fractional part can carry into integer position."""
        obj = _active_obj(x=100, vx=0, vy=0)
        obj.vx_frac = 0x8000   # 0.5 in fixed-point
        # Need two ticks for x to advance (0.5 + 0.5 = 1.0)
        update_position(obj)
        assert obj.x == 100     # not yet
        update_position(obj)
        assert obj.x == 101     # now!

    def test_wrap_right_edge(self):
        """Object near right edge wraps to left."""
        obj = _active_obj(x=VIRTUAL_W - WRAP_FACTOR - 1, vx=5)
        update_position(obj)
        # Should wrap to WRAP_FACTOR
        assert obj.x == WRAP_FACTOR

    def test_wrap_left_edge(self):
        """Object near left edge wraps to right."""
        obj = _active_obj(x=WRAP_FACTOR, vx=-5)
        update_position(obj)
        # Should wrap to right side
        assert obj.x == VIRTUAL_W - WRAP_FACTOR - 1

    def test_wrap_bottom_edge(self):
        """Object near bottom wraps to top."""
        obj = _active_obj(x=100, y=VIRTUAL_H - WRAP_FACTOR - 1, vy=5)
        update_position(obj)
        assert obj.y == WRAP_FACTOR

    def test_wrap_top_edge(self):
        """Object near top wraps to bottom."""
        obj = _active_obj(x=100, y=WRAP_FACTOR, vy=-5)
        update_position(obj)
        assert obj.y == VIRTUAL_H - WRAP_FACTOR - 1

    def test_inactive_object_not_moved(self):
        """Inactive object is skipped."""
        obj = _active_obj(x=100, vx=5)
        obj.eflg = EFLG_INACTIVE
        update_position(obj)
        assert obj.x == 100


class TestVelocityClamping:
    def test_thrust_clamps_vx(self):
        """Thrust cannot exceed MAX_X_VEL."""
        state = new_game_state()
        ship = state.objects[ENT_OBJ]
        ship.eflg = EFLG_ACTIVE
        ship.angle = 0          # pointing right → cos=max, sin=0
        ship.flags |= THRUST_BIT
        ship.vx = MAX_X_VEL    # already at max

        # After several thrust ticks, should stay at MAX_X_VEL
        for _ in range(20):
            apply_thrust(ship, 0)

        assert ship.vx <= MAX_X_VEL


class TestEnergyRecharge:
    def test_recharge_fires_at_blink_zero(self):
        """Energy recharges when blink wraps to 0."""
        state = new_game_state()
        ship = state.objects[ENT_OBJ]
        ship.energy = 50       # below max
        state.blink = 0

        _tick_energy_recharge(state)
        assert ship.energy == 51

    def test_recharge_not_at_other_blink(self):
        """Energy does not recharge at non-zero blink."""
        state = new_game_state()
        ship = state.objects[ENT_OBJ]
        ship.energy = 50
        state.blink = 1

        _tick_energy_recharge(state)
        assert ship.energy == 50

    def test_recharge_capped_at_max(self):
        """Energy does not exceed STARTING_ENERGY (127)."""
        state = new_game_state()
        ship = state.objects[ENT_OBJ]
        ship.energy = STARTING_ENERGY   # already at max
        state.blink = 0

        _tick_energy_recharge(state)
        assert ship.energy == STARTING_ENERGY

    def test_zero_energy_not_recharged(self):
        """Energy at 0 does not recharge (must use transfer)."""
        state = new_game_state()
        ship = state.objects[ENT_OBJ]
        ship.energy = 0
        state.blink = 0

        _tick_energy_recharge(state)
        # energy=0 is at the boundary; recharge only fires when 0 < energy < max
        assert ship.energy == 0


class TestTorpedoEnergyDrain:
    def test_drains_every_photon_time(self):
        """Active torpedo loses 1 energy every PHOTON_TIME ticks."""
        state = new_game_state()
        torp = state.objects[ENT_TORP_START]
        torp.eflg = EFLG_ACTIVE
        torp.energy = PHOTON_ENERGY

        state.blink = 0   # blink & (PHOTON_TIME-1) == 0 → drain fires
        _tick_torpedo_energy(state)
        assert torp.energy == PHOTON_ENERGY - 1

    def test_no_drain_at_wrong_tick(self):
        """No drain at non-PHOTON_TIME tick."""
        state = new_game_state()
        torp = state.objects[ENT_TORP_START]
        torp.eflg = EFLG_ACTIVE
        torp.energy = PHOTON_ENERGY

        state.blink = 1   # not aligned
        _tick_torpedo_energy(state)
        assert torp.energy == PHOTON_ENERGY

    def test_inactive_torp_not_drained(self):
        """Inactive torpedo energy is unchanged."""
        state = new_game_state()
        torp = state.objects[ENT_TORP_START]
        torp.eflg = EFLG_INACTIVE
        torp.energy = PHOTON_ENERGY

        state.blink = 0   # drain gate fires, but torp is inactive so skipped
        _tick_torpedo_energy(state)
        assert torp.energy == PHOTON_ENERGY

    def test_zero_energy_torp_explodes(self):
        """Torpedo with energy=1 explodes after drain."""
        state = new_game_state()
        torp = state.objects[ENT_TORP_START]
        torp.eflg = EFLG_ACTIVE
        torp.energy = 1

        state.blink = 0   # blink & (PHOTON_TIME-1) == 0 → drain fires
        _tick_torpedo_energy(state)
        assert torp.eflg == EFLG_EXPLODING


class TestPhaserStates:
    def test_idle_stays_idle(self):
        """PHASER_IDLE (255) does not change."""
        state = new_game_state()
        state.objects[ENT_OBJ].phaser_state = PHASER_IDLE
        _tick_phaser_states(state)
        assert state.objects[ENT_OBJ].phaser_state == PHASER_IDLE

    def test_countdown(self):
        """Non-idle, non-erase states decrement by 1."""
        state = new_game_state()
        state.objects[ENT_OBJ].phaser_state = 10
        _tick_phaser_states(state)
        assert state.objects[ENT_OBJ].phaser_state == 9

    def test_erase_state_not_decremented(self):
        """PHASER_ERASE (20) is skipped — main.py handles the erase."""
        state = new_game_state()
        state.objects[ENT_OBJ].phaser_state = PHASER_ERASE
        _tick_phaser_states(state)
        assert state.objects[ENT_OBJ].phaser_state == PHASER_ERASE

    def test_reaches_zero_resets_to_idle(self):
        """State reaching 0 → reset to PHASER_IDLE."""
        state = new_game_state()
        state.objects[ENT_OBJ].phaser_state = 1
        _tick_phaser_states(state)
        assert state.objects[ENT_OBJ].phaser_state == PHASER_IDLE
