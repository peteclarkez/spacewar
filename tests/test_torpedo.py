"""Tests for torpedo.py — photon torpedo firing logic."""

import pytest

from spacewar.init import new_game_state
from spacewar.torpedo import (
    fire_enterprise_torpedo, fire_klingon_torpedo, find_free_torpedo,
)
from spacewar.constants import (
    ENT_OBJ, KLN_OBJ,
    ENT_TORP_START, ENT_TORP_END,
    KLN_TORP_START, KLN_TORP_END,
    EFLG_ACTIVE, EFLG_INACTIVE,
    TORP_FIRE_BIT, PHOTON_LAUNCH_ENERGY, PHOTON_ENERGY,
    PHOTON_SOUND, STARTING_ENERGY,
)


class TestFindFreeTorpedo:
    def test_finds_first_inactive(self):
        state = new_game_state()
        # All torps start inactive
        idx = find_free_torpedo(state, ENT_TORP_START, ENT_TORP_END)
        assert idx == ENT_TORP_START

    def test_skips_active(self):
        state = new_game_state()
        state.objects[ENT_TORP_START].eflg = EFLG_ACTIVE
        idx = find_free_torpedo(state, ENT_TORP_START, ENT_TORP_END)
        assert idx == ENT_TORP_START + 1

    def test_all_active_returns_none(self):
        state = new_game_state()
        for i in range(ENT_TORP_START, ENT_TORP_END):
            state.objects[i].eflg = EFLG_ACTIVE
        idx = find_free_torpedo(state, ENT_TORP_START, ENT_TORP_END)
        assert idx is None

    def test_klingon_range(self):
        state = new_game_state()
        idx = find_free_torpedo(state, KLN_TORP_START, KLN_TORP_END)
        assert idx == KLN_TORP_START


class TestFireEnterpriseTorpedo:
    def test_successful_fire(self):
        """Happy path: torpedo is activated and ship energy decreases."""
        state = new_game_state()
        ship = state.objects[ENT_OBJ]
        ship.energy = STARTING_ENERGY
        energy_before = ship.energy

        fire_enterprise_torpedo(state)

        # One torpedo should now be active
        active_torps = [
            i for i in range(ENT_TORP_START, ENT_TORP_END)
            if state.objects[i].eflg == EFLG_ACTIVE
        ]
        assert len(active_torps) == 1

        # Ship energy reduced
        assert ship.energy == energy_before - PHOTON_LAUNCH_ENERGY

        # Torpedo has correct energy
        assert state.objects[active_torps[0]].energy == PHOTON_ENERGY

        # Sound flag set
        assert state.sound_flag & PHOTON_SOUND

    def test_no_fire_when_no_energy(self):
        """Cannot fire without energy."""
        state = new_game_state()
        state.objects[ENT_OBJ].energy = 0

        fire_enterprise_torpedo(state)

        active = sum(
            1 for i in range(ENT_TORP_START, ENT_TORP_END)
            if state.objects[i].eflg == EFLG_ACTIVE
        )
        assert active == 0

    def test_no_fire_when_all_slots_active(self):
        """Cannot fire when all 7 torpedo slots are occupied."""
        state = new_game_state()
        for i in range(ENT_TORP_START, ENT_TORP_END):
            state.objects[i].eflg = EFLG_ACTIVE

        fire_enterprise_torpedo(state)
        # No new torps added (all were already active)
        active = sum(
            1 for i in range(ENT_TORP_START, ENT_TORP_END)
            if state.objects[i].eflg == EFLG_ACTIVE
        )
        assert active == 7

    def test_torp_fire_debounce(self):
        """TORP_FIRE_BIT prevents double-firing."""
        state = new_game_state()
        state.objects[ENT_OBJ].fire |= TORP_FIRE_BIT

        fire_enterprise_torpedo(state)

        active = sum(
            1 for i in range(ENT_TORP_START, ENT_TORP_END)
            if state.objects[i].eflg == EFLG_ACTIVE
        )
        assert active == 0

    def test_torpedo_inherits_ship_velocity(self):
        """Torpedo velocity includes ship's current velocity."""
        state = new_game_state()
        ship = state.objects[ENT_OBJ]
        ship.angle = 0       # pointing right
        ship.vx = 3
        ship.vy = 0

        fire_enterprise_torpedo(state)

        active_idx = next(
            i for i in range(ENT_TORP_START, ENT_TORP_END)
            if state.objects[i].eflg == EFLG_ACTIVE
        )
        torp = state.objects[active_idx]
        # Torpedo vx should be >= ship vx (ship vel + fire impulse)
        assert torp.vx >= ship.vx

    def test_torpedo_position_near_ship(self):
        """Torpedo spawns near the firing ship."""
        state = new_game_state()
        ship = state.objects[ENT_OBJ]
        ship.x, ship.y = 200, 100
        ship.angle = 0

        fire_enterprise_torpedo(state)

        active_idx = next(
            (i for i in range(ENT_TORP_START, ENT_TORP_END)
             if state.objects[i].eflg == EFLG_ACTIVE),
            None,
        )
        assert active_idx is not None
        torp = state.objects[active_idx]
        assert abs(torp.x - ship.x) < 20
        assert abs(torp.y - ship.y) < 20


class TestFireKlingonTorpedo:
    def test_fires_in_klingon_slots(self):
        """Klingon torpedo goes into slots 9-15."""
        state = new_game_state()

        fire_klingon_torpedo(state)

        active = [
            i for i in range(KLN_TORP_START, KLN_TORP_END)
            if state.objects[i].eflg == EFLG_ACTIVE
        ]
        assert len(active) == 1
        # Confirm no Enterprise torp was activated
        ent_active = [
            i for i in range(ENT_TORP_START, ENT_TORP_END)
            if state.objects[i].eflg == EFLG_ACTIVE
        ]
        assert len(ent_active) == 0
