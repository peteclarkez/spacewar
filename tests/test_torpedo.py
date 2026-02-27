"""
Tests for torpedo.py — launch, physics, lifespan, pool management, collisions.
"""

import pytest
from spacewar.torpedo import Torpedo, TorpedoPool
from spacewar.constants import (
    PHOTON_ENERGY, PHOTON_TIME, MAX_TORPS,
    SHIP_TO_TORP_RANGE, TORP_TO_TORP_RANGE,
    PLAYER_ENT, PLAYER_KLN,
)


class TestTorpedoLaunch:
    def test_inactive_by_default(self):
        t = Torpedo()
        assert not t.active

    def test_launch_activates(self):
        t = Torpedo()
        t.launch(100.0, 50.0, 0.0, 0.0, 0, PLAYER_ENT)
        assert t.active
        assert not t.exploding

    def test_initial_energy(self):
        t = Torpedo()
        t.launch(100.0, 50.0, 0.0, 0.0, 0, PLAYER_ENT)
        assert t.energy == PHOTON_ENERGY

    def test_velocity_inherits_ship(self):
        t = Torpedo()
        t.launch(100.0, 50.0, 3.0, 1.0, 0, PLAYER_ENT)
        # Torpedo velocity should be > ship velocity in facing direction
        assert t.vx > 3.0

    def test_spawn_offset_applied(self):
        t = Torpedo()
        # Angle 0 = East → torpedo spawns to the right of ship
        t.launch(100.0, 50.0, 0.0, 0.0, 0, PLAYER_ENT)
        assert t.x > 100.0    # offset forward

    def test_owner_recorded(self):
        t = Torpedo()
        t.launch(100.0, 50.0, 0.0, 0.0, 0, PLAYER_KLN)
        assert t.owner == PLAYER_KLN

    def test_reset(self):
        t = Torpedo()
        t.launch(100.0, 50.0, 0.0, 0.0, 0, PLAYER_ENT)
        t.reset()
        assert not t.active
        assert t.energy == 0


class TestTorpedoUpdate:
    def test_moves_each_tick(self):
        t = Torpedo()
        t.launch(200.0, 100.0, 0.0, 0.0, 0, PLAYER_ENT)
        x0 = t.x
        t.update(gravity_on=False, tick=1)
        assert t.x != x0

    def test_energy_drains_on_period(self):
        t = Torpedo()
        t.launch(200.0, 100.0, 0.0, 0.0, 0, PLAYER_ENT)
        initial = t.energy
        # tick=PHOTON_TIME → first drain
        t.update(gravity_on=False, tick=PHOTON_TIME)
        assert t.energy == initial - 1

    def test_no_drain_off_period(self):
        t = Torpedo()
        t.launch(200.0, 100.0, 0.0, 0.0, 0, PLAYER_ENT)
        initial = t.energy
        t.update(gravity_on=False, tick=1)
        assert t.energy == initial

    def test_explodes_when_energy_zero(self):
        t = Torpedo()
        t.launch(200.0, 100.0, 0.0, 0.0, 0, PLAYER_ENT)
        t.energy = 1
        t.update(gravity_on=False, tick=PHOTON_TIME)
        assert t.exploding

    def test_gravity_affects_velocity(self):
        from spacewar.constants import PLANET_X, PLANET_Y
        t = Torpedo()
        t.launch(PLANET_X + 200, PLANET_Y, 0.0, 0.0, 0, PLAYER_ENT)
        vx0 = t.vx
        t.update(gravity_on=True, tick=1)
        assert t.vx < vx0   # pulled leftward toward planet

    def test_explosion_animation_advances(self):
        t = Torpedo()
        t.launch(200.0, 100.0, 0.0, 0.0, 0, PLAYER_ENT)
        t.begin_explosion()
        assert t.exploding
        t0 = t.exptick
        t.update(gravity_on=False, tick=1)
        assert t.exptick > t0

    def test_explosion_deactivates_after_anim(self):
        t = Torpedo()
        t.launch(200.0, 100.0, 0.0, 0.0, 0, PLAYER_ENT)
        t.begin_explosion()
        for i in range(40):
            t.update(gravity_on=False, tick=i)
        assert not t.active


class TestTorpedoPool:
    def test_fire_succeeds_in_empty_pool(self, ent_torps):
        ok = ent_torps.fire(200.0, 100.0, 0.0, 0.0, 0)
        assert ok

    def test_fire_uses_first_free_slot(self, ent_torps):
        ent_torps.fire(200.0, 100.0, 0.0, 0.0, 0)
        actives = ent_torps.active_torpedoes()
        assert len(actives) == 1

    def test_fire_fills_all_slots(self, ent_torps):
        for _ in range(MAX_TORPS):
            assert ent_torps.fire(200.0, 100.0, 0.0, 0.0, 0)

    def test_fire_blocked_when_full(self, ent_torps):
        for _ in range(MAX_TORPS):
            ent_torps.fire(200.0, 100.0, 0.0, 0.0, 0)
        ok = ent_torps.fire(200.0, 100.0, 0.0, 0.0, 0)
        assert not ok

    def test_reset_clears_all(self, ent_torps):
        for _ in range(MAX_TORPS):
            ent_torps.fire(200.0, 100.0, 0.0, 0.0, 0)
        ent_torps.reset()
        assert len(ent_torps.active_torpedoes()) == 0

    def test_update_advances_torpedoes(self, ent_torps):
        ent_torps.fire(200.0, 100.0, 0.0, 0.0, 0)
        t = ent_torps.slots[0]
        x0 = t.x
        ent_torps.update(gravity_on=False, tick=1)
        assert t.x != x0

    def test_active_torpedoes_excludes_exploding(self, ent_torps):
        ent_torps.fire(200.0, 100.0, 0.0, 0.0, 0)
        ent_torps.slots[0].begin_explosion()
        assert len(ent_torps.active_torpedoes()) == 0

    def test_owner_propagated(self, kln_torps):
        kln_torps.fire(200.0, 100.0, 0.0, 0.0, 128)
        assert kln_torps.slots[0].owner == PLAYER_KLN


class TestExplosion:
    def test_begin_explosion(self):
        t = Torpedo()
        t.launch(200.0, 100.0, 0.0, 0.0, 0, PLAYER_ENT)
        t.begin_explosion()
        assert t.exploding
        assert t.active    # still active during animation
        assert t.exptick == 0

    def test_begin_planet_hit(self):
        t = Torpedo()
        t.launch(200.0, 100.0, 0.0, 0.0, 0, PLAYER_ENT)
        t.begin_planet_hit()
        assert t.exploding

    def test_is_alive_false_when_exploding(self):
        t = Torpedo()
        t.launch(200.0, 100.0, 0.0, 0.0, 0, PLAYER_ENT)
        assert t.is_alive
        t.begin_explosion()
        assert not t.is_alive
