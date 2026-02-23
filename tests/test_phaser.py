"""Tests for phaser.py — phaser firing, state machine, and hit detection."""

import pytest

from spacewar.init import new_game_state, GameObject
from spacewar.constants import (
    ENT_OBJ, KLN_OBJ,
    ENT_TORP_START,
    EFLG_ACTIVE, EFLG_INACTIVE, EFLG_EXPLODING,
    PHASER_IDLE, PHASER_DELAY, PHASER_RANGE, PHASER_ERASE,
    PHASER_FIRE_ENERGY, PHASER_DAMAGE, PHASER_TO_OBJ_RANGE,
    PHASER_SOUND, STARTING_ENERGY, STARTING_SHIELDS,
)


# ---------------------------------------------------------------------------
# Minimal pygame surface stub so phaser tests don't need a display
# ---------------------------------------------------------------------------

class _FakeSurface:
    """Minimal pygame.Surface stand-in for unit tests."""

    def __init__(self, w=640, h=480):
        self._w = w
        self._h = h
        self.pixels: dict[tuple, tuple] = {}

    def get_width(self):
        return self._w

    def get_height(self):
        return self._h

    def set_at(self, pos, color):
        self.pixels[pos] = color


class TestPhaserFire:
    def test_fire_sets_state(self):
        """Firing sets phaser_state to PHASER_DELAY and deducts energy."""
        from spacewar.phaser import fire_phaser_enterprise
        state = new_game_state()
        ship = state.objects[ENT_OBJ]
        ship.eflg = EFLG_ACTIVE
        ship.energy = STARTING_ENERGY
        surf = _FakeSurface()

        fire_phaser_enterprise(state, surf)

        assert ship.phaser_state == PHASER_DELAY
        assert ship.energy == STARTING_ENERGY - PHASER_FIRE_ENERGY

    def test_fire_sets_phaser_sound(self):
        from spacewar.phaser import fire_phaser_enterprise
        state = new_game_state()
        state.objects[ENT_OBJ].energy = STARTING_ENERGY
        surf = _FakeSurface()

        fire_phaser_enterprise(state, surf)

        assert state.sound_flag & PHASER_SOUND

    def test_fire_saves_origin(self):
        """phaser_x/y/angle saved from ship position at fire time."""
        from spacewar.phaser import fire_phaser_enterprise
        state = new_game_state()
        ship = state.objects[ENT_OBJ]
        ship.x, ship.y, ship.angle = 150, 75, 32
        ship.energy = STARTING_ENERGY
        surf = _FakeSurface()

        fire_phaser_enterprise(state, surf)

        assert ship.phaser_x == 150
        assert ship.phaser_y == 75
        assert ship.phaser_angle == 32

    def test_no_fire_when_energy_zero(self):
        """Cannot fire with zero energy."""
        from spacewar.phaser import fire_phaser_enterprise
        state = new_game_state()
        state.objects[ENT_OBJ].energy = 0
        surf = _FakeSurface()

        fire_phaser_enterprise(state, surf)

        assert state.objects[ENT_OBJ].phaser_state == PHASER_IDLE

    def test_no_fire_during_cooldown(self):
        """Cannot fire when phaser_state != PHASER_IDLE."""
        from spacewar.phaser import fire_phaser_enterprise
        state = new_game_state()
        state.objects[ENT_OBJ].energy = STARTING_ENERGY
        state.objects[ENT_OBJ].phaser_state = 10   # still cooling down
        surf = _FakeSurface()

        fire_phaser_enterprise(state, surf)

        # State should not change
        assert state.objects[ENT_OBJ].phaser_state == 10

    def test_klingon_fire(self):
        """Klingon phaser fires symmetrically."""
        from spacewar.phaser import fire_phaser_klingon
        state = new_game_state()
        kln = state.objects[KLN_OBJ]
        kln.energy = STARTING_ENERGY
        surf = _FakeSurface()

        fire_phaser_klingon(state, surf)

        assert kln.phaser_state == PHASER_DELAY
        assert kln.energy == STARTING_ENERGY - PHASER_FIRE_ENERGY


class TestPhaserRay:
    def test_ray_draws_pixels(self):
        """Firing should draw pixels on the surface."""
        from spacewar.phaser import fire_phaser_enterprise
        state = new_game_state()
        ship = state.objects[ENT_OBJ]
        ship.x, ship.y = 100, 50
        ship.angle = 0   # pointing right
        ship.energy = STARTING_ENERGY
        surf = _FakeSurface()

        fire_phaser_enterprise(state, surf)

        assert len(surf.pixels) > 0

    def test_ray_length_capped_at_phaser_range(self):
        """Ray never extends beyond PHASER_RANGE pixels."""
        from spacewar.phaser import fire_phaser_enterprise
        state = new_game_state()
        ship = state.objects[ENT_OBJ]
        ship.x, ship.y = 100, 50
        ship.angle = 0
        ship.energy = STARTING_ENERGY
        surf = _FakeSurface()

        fire_phaser_enterprise(state, surf)

        assert ship.phaser_count <= PHASER_RANGE

    def test_phaser_count_stored(self):
        """phaser_count is set to the actual ray length drawn."""
        from spacewar.phaser import fire_phaser_enterprise
        state = new_game_state()
        state.objects[ENT_OBJ].x = 100
        state.objects[ENT_OBJ].y = 50
        state.objects[ENT_OBJ].angle = 0
        state.objects[ENT_OBJ].energy = STARTING_ENERGY
        surf = _FakeSurface()

        fire_phaser_enterprise(state, surf)

        assert state.objects[ENT_OBJ].phaser_count > 0


class TestPhaserHitDetection:
    def test_ship_in_range_loses_shields(self):
        """Target ship within PHASER_TO_OBJ_RANGE of ray loses PHASER_DAMAGE shields."""
        from spacewar.phaser import fire_phaser_enterprise
        state = new_game_state()
        ship = state.objects[ENT_OBJ]
        ship.x, ship.y = 100, 50
        ship.angle = 0   # pointing right
        ship.energy = STARTING_ENERGY

        # Place Klingon ship directly in the ray path
        kln = state.objects[KLN_OBJ]
        kln.x = 130   # 30px to the right — well within range=96
        kln.y = 50    # same row
        kln.eflg = EFLG_ACTIVE
        kln.shields = STARTING_SHIELDS

        surf = _FakeSurface()
        fire_phaser_enterprise(state, surf)

        assert kln.shields < STARTING_SHIELDS

    def test_torpedo_in_range_explodes(self):
        """Torpedo within PHASER_TO_OBJ_RANGE of ray check point explodes."""
        from spacewar.phaser import fire_phaser_enterprise
        state = new_game_state()
        ship = state.objects[ENT_OBJ]
        ship.x, ship.y = 100, 50
        ship.angle = 0
        ship.energy = STARTING_ENERGY

        torp = state.objects[ENT_TORP_START]
        torp.x = 130
        torp.y = 50
        torp.eflg = EFLG_ACTIVE

        surf = _FakeSurface()
        fire_phaser_enterprise(state, surf)

        assert torp.eflg == EFLG_EXPLODING

    def test_erase_does_not_hit(self):
        """Erase pass (compare=False) should not damage any objects."""
        from spacewar.phaser import fire_phaser_enterprise, erase_phaser_enterprise
        state = new_game_state()
        ship = state.objects[ENT_OBJ]
        ship.x, ship.y = 100, 50
        ship.angle = 0
        ship.energy = STARTING_ENERGY

        kln = state.objects[KLN_OBJ]
        kln.x = 130
        kln.y = 50
        kln.eflg = EFLG_ACTIVE
        kln.shields = STARTING_SHIELDS

        surf = _FakeSurface()

        # First do a fire (to set up phaser_count etc.)
        fire_phaser_enterprise(state, surf)
        shields_after_fire = kln.shields

        # Now erase — should not change shields further
        erase_phaser_enterprise(state, surf)
        assert kln.shields == shields_after_fire
