"""
Tests for game.py — collision detection logic, scoring, mode transitions.

Game.init_display() is NOT called; we test the logic methods directly
by instantiating Game without a window and exercising its internals.
"""

import os
import pytest

from spacewar.game import Game, Mode
from spacewar.ship import Ship
from spacewar.constants import (
    PHOTON_DAMAGE, PHASER_DAMAGE, PLANET_DAMAGE,
    SHIP_TO_SHIP_RANGE, SHIP_TO_TORP_RANGE, TORP_TO_TORP_RANGE,
    PLANET_X, PLANET_Y, PLANET_RANGE, BOUNCE_FACTOR,
    STARTING_SHIELDS,
    PLAYER_ENT, PLAYER_KLN,
)


@pytest.fixture()
def game():
    """Game instance with display NOT initialised (headless logic tests)."""
    g = Game(scale=1, neon=False)
    return g


class TestModeTransitions:
    def test_initial_mode_is_attract(self, game):
        assert game.mode == Mode.ATTRACT

    def test_start_game_enters_play(self, game):
        game._start_game()
        assert game.mode == Mode.PLAY

    def test_enter_attract_from_play(self, game):
        game._start_game()
        game._enter_attract()
        assert game.mode == Mode.ATTRACT

    def test_start_game_resets_ships(self, game):
        game._start_game()
        from spacewar.constants import ENT_START_X, KLN_START_X
        assert game.ent.x == ENT_START_X
        assert game.kln.x == KLN_START_X

    def test_start_game_preserves_scores(self, game):
        game.ent_score = 3
        game.kln_score = 5
        game._start_game()
        assert game.ent_score == 3
        assert game.kln_score == 5

    def test_start_game_resets_tick(self, game):
        game.tick = 9999
        game._start_game()
        assert game.tick == 0


class TestShipShipCollision:
    def _place_ships(self, game, ent_x, ent_y, kln_x, kln_y):
        game._start_game()
        game.ent.x, game.ent.y = ent_x, ent_y
        game.kln.x, game.kln.y = kln_x, kln_y
        game.ent.vx, game.ent.vy = 2.0, 0.0
        game.kln.vx, game.kln.vy = -1.0, 0.0

    def test_no_collision_far_apart(self, game):
        game._start_game()
        game.ent.x, game.ent.y = 100.0, 100.0
        game.kln.x, game.kln.y = 400.0, 100.0
        evx0 = game.ent.vx
        game._check_ship_ship()
        assert game.ent.vx == evx0   # unchanged

    def test_collision_swaps_velocity(self, game):
        self._place_ships(game, 300.0, 100.0, 300.0 + SHIP_TO_SHIP_RANGE - 1, 100.0)
        evx0 = game.ent.vx
        kvx0 = game.kln.vx
        game._check_ship_ship()
        # Each ship takes half the other's velocity
        assert game.ent.vx == pytest.approx(kvx0 * 0.5)
        assert game.kln.vx == pytest.approx(evx0 * 0.5)

    def test_collision_pushes_apart(self, game):
        self._place_ships(game, 300.0, 100.0, 300.0 + SHIP_TO_SHIP_RANGE - 1, 100.0)
        ex0, kx0 = game.ent.x, game.kln.x
        game._check_ship_ship()
        # Ships should be pushed further apart
        assert game.ent.x <= ex0
        assert game.kln.x >= kx0

    def test_no_shield_damage_on_collision(self, game):
        self._place_ships(game, 300.0, 100.0, 300.0 + SHIP_TO_SHIP_RANGE - 1, 100.0)
        es0, ks0 = game.ent.shields, game.kln.shields
        game._check_ship_ship()
        assert game.ent.shields == es0
        assert game.kln.shields == ks0


class TestTorpedoCollision:
    def test_torpedo_hits_opponent(self, game):
        game._start_game()
        game.kln.x, game.kln.y = 200.0, 100.0
        # Fire a klingon torpedo right on top of the enterprise
        game.kln_torps.fire(game.ent.x, game.ent.y, 0.0, 0.0, 0)
        t = game.kln_torps.slots[0]
        t.x, t.y = game.ent.x, game.ent.y   # place directly on ent
        initial_shields = game.ent.shields
        game._check_collisions()
        assert game.ent.shields == initial_shields - PHOTON_DAMAGE

    def test_own_torpedo_can_hit_self(self, game):
        """Per spec: self-hit is allowed for all torp combinations."""
        game._start_game()
        game.ent_torps.fire(game.ent.x, game.ent.y, 0.0, 0.0, 0)
        t = game.ent_torps.slots[0]
        t.x, t.y = game.ent.x, game.ent.y
        initial_shields = game.ent.shields
        game._check_collisions()
        assert game.ent.shields == initial_shields - PHOTON_DAMAGE

    def test_torp_torp_annihilation(self, game):
        game._start_game()
        game.ent_torps.fire(300.0, 100.0, 0.0, 0.0, 0)
        game.kln_torps.fire(300.0, 100.0, 0.0, 0.0, 0)
        et = game.ent_torps.slots[0]
        kt = game.kln_torps.slots[0]
        et.x, et.y = 300.0, 100.0
        kt.x, kt.y = 300.0, 100.0
        game._check_collisions()
        assert et.exploding
        assert kt.exploding


class TestPlanetHazard:
    def test_ship_near_planet_takes_damage(self, game):
        game._start_game()
        game.state.planet_on = True
        game.ent.x, game.ent.y = float(PLANET_X), float(PLANET_Y)
        initial = game.ent.shields
        game._check_planet_hazard()
        assert game.ent.shields == initial - PLANET_DAMAGE

    def test_ship_far_from_planet_safe(self, game):
        game._start_game()
        game.state.planet_on = True
        game.ent.x, game.ent.y = 0.0, 0.0
        initial = game.ent.shields
        game._check_planet_hazard()
        assert game.ent.shields == initial

    def test_torpedo_at_planet_explodes(self, game):
        game._start_game()
        game.state.planet_on = True
        game.ent_torps.fire(float(PLANET_X), float(PLANET_Y), 0.0, 0.0, 0)
        t = game.ent_torps.slots[0]
        t.x, t.y = float(PLANET_X), float(PLANET_Y)
        game._check_planet_hazard()
        assert t.exploding


class TestDeath:
    def test_death_increments_opponent_score(self, game):
        game._start_game()
        assert game.kln_score == 0
        game._handle_death(game.ent)
        assert game.kln_score == 1

    def test_death_triggers_explosion(self, game):
        game._start_game()
        game._handle_death(game.ent)
        assert game.ent.particles.active

    def test_death_sets_dead_flag(self, game):
        game._start_game()
        game._handle_death(game.ent)
        assert game.ent.dead
        assert not game.ent.alive


class TestHyperspace:
    def test_hyperspace_teleports_ship(self, game):
        game._start_game()
        from spacewar.physics import ParticleSystem
        from spacewar.constants import HYPER_DURATION

        dest_x, dest_y = 400.0, 150.0
        game.ent.particles.start_hyperspace(game.ent.x, game.ent.y, dest_x, dest_y)
        game.ent.alive = False

        # Advance through full animation
        for _ in range(HYPER_DURATION + 2):
            game.ent.particles.update()

        # Simulate hyperspace completion
        game._restore_from_hyperspace(game.ent)
        assert game.ent.x == dest_x
        assert game.ent.y == dest_y
        assert game.ent.vx == 0.0
        assert game.ent.vy == 0.0
        assert game.ent.alive


class TestStateToggles:
    def test_toggle_sound(self, game):
        initial = game.state.sound_on
        game._toggle_sound()
        assert game.state.sound_on == (not initial)

    def test_pause_toggle(self, game):
        assert not game.state.paused
        game.state.paused = True
        assert game.state.paused

    def test_gravity_defaults_on(self, game):
        assert game.state.gravity_on

    def test_planet_defaults_on(self, game):
        assert game.state.planet_on
