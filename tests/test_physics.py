"""Tests for physics.py — position integration, energy, timing."""

import pytest

from spacewar.init import GameObject, GameState, new_game_state
from spacewar.physics import (
    run_physics_tick, update_position, apply_thrust, apply_cloak_drain,
    _tick_energy_recharge, _tick_torpedo_energy, _tick_phaser_states,
    _update_angles, _clamp_velocity,
    _tick_shield_warning, _tick_explosions, _tick_planet_animation,
    _tick_hyperspace,
)
from spacewar.constants import (
    VIRTUAL_W, VIRTUAL_H, WRAP_FACTOR,
    MAX_X_VEL, MAX_Y_VEL,
    ACCEL_SCALE, THRUST_BIT, CLOAK_BIT,
    EFLG_ACTIVE, EFLG_INACTIVE, EFLG_EXPLODING,
    ENT_OBJ, KLN_OBJ,
    ENT_TORP_START, ENT_TORP_END,
    PHASER_IDLE, PHASER_ERASE,
    STARTING_ENERGY,
    PHOTON_ENERGY, PHOTON_TIME, DILITHIUM_TIME,
    CLOAK_TIME, WARNING_TIME, PLANET_TIME,
    WARNING_SOUND, LOW_SHIELD_LIMIT,
    HYPER_DURATION, HYPER_PHASE, HYPER_PARTICLES,
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


class TestUpdateAngles:
    def test_angle_advances_by_rotate(self):
        state = new_game_state()
        ship = state.objects[ENT_OBJ]
        ship.angle = 10
        ship.rotate = 3
        _update_angles(state)
        assert ship.angle == 13

    def test_angle_wraps_at_256(self):
        state = new_game_state()
        ship = state.objects[ENT_OBJ]
        ship.angle = 254
        ship.rotate = 4
        _update_angles(state)
        assert ship.angle == (254 + 4) & 0xFF

    def test_inactive_ship_not_updated(self):
        state = new_game_state()
        ship = state.objects[ENT_OBJ]
        ship.angle = 10
        ship.rotate = 3
        ship.eflg = EFLG_INACTIVE
        _update_angles(state)
        assert ship.angle == 10   # unchanged

    def test_klingon_angle_updated(self):
        state = new_game_state()
        kln = state.objects[KLN_OBJ]
        kln.angle = 100
        kln.rotate = 5
        _update_angles(state)
        assert kln.angle == 105


class TestClampVelocity:
    def test_vx_over_max_clamped(self):
        obj = GameObject()
        obj.vx = MAX_X_VEL + 5
        obj.vx_frac = 0x8000
        _clamp_velocity(obj)
        assert obj.vx == MAX_X_VEL
        assert obj.vx_frac == 0

    def test_vx_under_neg_max_clamped(self):
        obj = GameObject()
        obj.vx = -(MAX_X_VEL + 3)
        obj.vx_frac = 0x8000
        _clamp_velocity(obj)
        assert obj.vx == -MAX_X_VEL
        assert obj.vx_frac == 0

    def test_vy_over_max_clamped(self):
        obj = GameObject()
        obj.vy = MAX_Y_VEL + 2
        obj.vy_frac = 0x1000
        _clamp_velocity(obj)
        assert obj.vy == MAX_Y_VEL
        assert obj.vy_frac == 0

    def test_vy_under_neg_max_clamped(self):
        obj = GameObject()
        obj.vy = -(MAX_Y_VEL + 1)
        obj.vy_frac = 0xAAAA
        _clamp_velocity(obj)
        assert obj.vy == -MAX_Y_VEL
        assert obj.vy_frac == 0

    def test_within_range_unchanged(self):
        obj = GameObject()
        obj.vx = 3
        obj.vy = -2
        _clamp_velocity(obj)
        assert obj.vx == 3
        assert obj.vy == -2


class TestApplyThrustNoThrust:
    def test_no_thrust_bit_returns_immediately(self):
        """apply_thrust is a no-op when THRUST_BIT is not set."""
        state = new_game_state()
        ship = state.objects[ENT_OBJ]
        ship.vx = 0
        ship.vy = 0
        ship.flags = 0   # no THRUST_BIT
        apply_thrust(ship, 0)
        assert ship.vx == 0
        assert ship.vy == 0


class TestApplyCloakDrain:
    def test_no_cloak_no_drain(self):
        state = new_game_state()
        ship = state.objects[ENT_OBJ]
        ship.energy = 100
        ship.flags = 0   # CLOAK_BIT not set
        apply_cloak_drain(ship, 0)
        assert ship.energy == 100

    def test_cloak_drains_at_interval(self):
        state = new_game_state()
        ship = state.objects[ENT_OBJ]
        ship.energy = 50
        ship.flags |= CLOAK_BIT
        # blink=0: 0 & (CLOAK_TIME-1) == 0 → drain fires
        apply_cloak_drain(ship, 0)
        assert ship.energy == 49

    def test_cloak_no_drain_off_interval(self):
        state = new_game_state()
        ship = state.objects[ENT_OBJ]
        ship.energy = 50
        ship.flags |= CLOAK_BIT
        apply_cloak_drain(ship, 1)   # not on a CLOAK_TIME boundary
        assert ship.energy == 50

    def test_cloak_auto_disabled_at_zero_energy(self):
        state = new_game_state()
        ship = state.objects[ENT_OBJ]
        ship.energy = 0
        ship.flags |= CLOAK_BIT
        apply_cloak_drain(ship, 0)   # drain interval fires, energy=0
        assert not (ship.flags & CLOAK_BIT)


class TestShieldWarning:
    def test_warning_set_when_shields_low(self):
        state = new_game_state()
        ship = state.objects[ENT_OBJ]
        ship.shields = LOW_SHIELD_LIMIT - 1
        state.blink = 0   # 0 & (WARNING_TIME-1) == 0
        _tick_shield_warning(state)
        assert state.sound_flag & WARNING_SOUND

    def test_warning_cleared_when_shields_ok(self):
        state = new_game_state()
        state.sound_flag |= WARNING_SOUND   # pre-set
        ship = state.objects[ENT_OBJ]
        ship.shields = LOW_SHIELD_LIMIT
        state.blink = 0
        _tick_shield_warning(state)
        assert not (state.sound_flag & WARNING_SOUND)

    def test_no_change_off_interval(self):
        state = new_game_state()
        state.sound_flag = 0
        ship = state.objects[ENT_OBJ]
        ship.shields = 0   # very low
        state.blink = 1   # not on a WARNING_TIME boundary
        _tick_shield_warning(state)
        assert not (state.sound_flag & WARNING_SOUND)


class TestTickExplosions:
    def test_exps_decremented(self):
        state = new_game_state()
        obj = state.objects[ENT_OBJ]
        obj.eflg = EFLG_EXPLODING
        obj.exps = 5
        _tick_explosions(state)
        assert obj.exps == 4
        assert obj.eflg == EFLG_EXPLODING

    def test_exps_zero_becomes_inactive(self):
        state = new_game_state()
        obj = state.objects[ENT_OBJ]
        obj.eflg = EFLG_EXPLODING
        obj.exps = 1
        _tick_explosions(state)
        assert obj.exps == 0
        assert obj.eflg == EFLG_INACTIVE

    def test_active_object_unchanged(self):
        state = new_game_state()
        obj = state.objects[ENT_OBJ]
        obj.eflg = EFLG_ACTIVE
        obj.exps = 0
        _tick_explosions(state)
        assert obj.eflg == EFLG_ACTIVE

    def test_exploding_with_zero_exps_unchanged(self):
        """Real hyperspace ships have eflg=EXPLODING and exps=0 — must not become INACTIVE."""
        state = new_game_state()
        obj = state.objects[ENT_OBJ]
        obj.eflg = EFLG_EXPLODING
        obj.exps = 0
        _tick_explosions(state)
        assert obj.eflg == EFLG_EXPLODING   # must not be set to INACTIVE


class TestPlanetAnimation:
    def test_frame_advances_at_planet_time(self):
        state = new_game_state()
        state.planet_state = 0
        state.blink = 0   # 0 & (PLANET_TIME-1) == 0
        _tick_planet_animation(state)
        assert state.planet_state == 1

    def test_frame_wraps_at_16(self):
        state = new_game_state()
        state.planet_state = 15
        state.blink = 0
        _tick_planet_animation(state)
        assert state.planet_state == 0

    def test_no_advance_off_interval(self):
        state = new_game_state()
        state.planet_state = 5
        state.blink = 1
        _tick_planet_animation(state)
        assert state.planet_state == 5


class TestHyperspace:
    def _setup_hyper(self, flag_start=1, dest_x=400, dest_y=100):
        """Set up state with ENT in real hyperspace, particles active.

        Real hyperspace sets eflg=EFLG_EXPLODING (to hide the ship during transit)
        and exps=0 (death explosions use exps>0 to distinguish themselves).
        """
        state = new_game_state()
        ship = state.objects[ENT_OBJ]
        ship.x = 100
        ship.y = 50
        ship.vx = ship.vy = 0
        ship.eflg = EFLG_EXPLODING   # real hyperspace — hidden during transit
        ship.exps = 0
        state.hyper_ent_flag = flag_start
        state.hyper_ent_dest_x = dest_x
        state.hyper_ent_dest_y = dest_y
        for p in state.hyper_particles[:HYPER_PARTICLES]:
            p.x = float(ship.x)
            p.y = float(ship.y)
            p.vx = 1.0
            p.vy = 0.5
            p.active = True
        return state

    def test_flag_zero_skipped(self):
        """flag == 0 means no active hyperspace; nothing changes."""
        state = new_game_state()
        state.hyper_ent_flag = 0
        state.hyper_particles[0].x = 10.0
        _tick_hyperspace(state)
        assert state.hyper_ent_flag == 0
        assert state.hyper_particles[0].x == 10.0

    def test_particles_advance_during_expansion(self):
        """In phase 1, particles move by their velocity each tick."""
        state = self._setup_hyper(flag_start=1)
        px_before = state.hyper_particles[0].x
        _tick_hyperspace(state)
        # flag went 1→2 (not at HYPER_PHASE+1), so particles advance
        assert state.hyper_particles[0].x == px_before + 1.0

    def test_velocity_recalculated_at_phase_transition(self):
        """At HYPER_PHASE+1, particle velocities are recalculated toward dest."""
        state = self._setup_hyper(flag_start=HYPER_PHASE, dest_x=400, dest_y=100)
        # Give particles a position far from dest
        for p in state.hyper_particles[:HYPER_PARTICLES]:
            p.x = 100.0
            p.y = 50.0
        _tick_hyperspace(state)
        # flag now == HYPER_PHASE+1 → velocity recalculated
        p = state.hyper_particles[0]
        expected_vx = (400.0 - 100.0) / HYPER_PHASE
        expected_vy = (100.0 - 50.0) / HYPER_PHASE
        assert abs(p.vx - expected_vx) < 0.01
        assert abs(p.vy - expected_vy) < 0.01

    def test_ship_teleports_at_completion(self):
        """At HYPER_DURATION, ship teleports, velocity zeroes, flag resets."""
        state = self._setup_hyper(flag_start=HYPER_DURATION, dest_x=300, dest_y=120)
        _tick_hyperspace(state)
        ship = state.objects[ENT_OBJ]
        assert ship.x == 300
        assert ship.y == 120
        assert ship.vx == 0 and ship.vy == 0
        assert ship.eflg == EFLG_ACTIVE
        assert state.hyper_ent_flag == 0

    def test_death_explosion_no_teleport(self):
        """Death explosion: particles expand, but ship never teleports.

        Two cases:
          - Mid-animation: eflg=EXPLODING, exps>0
          - Final frame:   eflg=INACTIVE,  exps=0  (after _tick_explosions ran)
        """
        # Mid-animation case: exps > 0
        state = self._setup_hyper(flag_start=HYPER_DURATION, dest_x=300, dest_y=120)
        state.objects[ENT_OBJ].exps = 10   # death explosion still counting
        _tick_hyperspace(state)
        ship = state.objects[ENT_OBJ]
        assert ship.x != 300 or ship.y != 120, "Teleport occurred mid-animation"
        assert state.hyper_ent_flag != 0, "Flag was reset mid-animation"

        # Final frame case: _tick_explosions already set eflg=INACTIVE, exps=0
        state = self._setup_hyper(flag_start=HYPER_DURATION, dest_x=300, dest_y=120)
        state.objects[ENT_OBJ].eflg = EFLG_INACTIVE
        state.objects[ENT_OBJ].exps = 0
        _tick_hyperspace(state)
        ship = state.objects[ENT_OBJ]
        assert ship.x != 300 or ship.y != 120, "Teleport occurred on final frame"
        assert state.hyper_ent_flag != 0, "Flag was reset on final frame"


class TestRunPhysicsTick:
    def test_blink_advances(self):
        state = new_game_state()
        state.blink = 0
        run_physics_tick(state)
        assert state.blink == 1

    def test_blink_wraps_at_256(self):
        state = new_game_state()
        state.blink = 255
        run_physics_tick(state)
        assert state.blink == 0

    def test_pause_skips_physics(self):
        """When paused, blink still advances but positions do not change."""
        state = new_game_state()
        ship = state.objects[ENT_OBJ]
        ship.vx = 5
        state.pause_enable = True
        x_before = ship.x
        run_physics_tick(state)
        assert ship.x == x_before   # position frozen

    def test_ship_position_updates_when_not_paused(self):
        state = new_game_state()
        ship = state.objects[ENT_OBJ]
        ship.vx = 2
        x_before = ship.x
        run_physics_tick(state)
        assert ship.x == x_before + 2

    def test_planet_animation_advances(self):
        """Planet frame increments at PLANET_TIME boundary inside full tick."""
        state = new_game_state()
        # Set blink so that after the +1 it lands on a PLANET_TIME boundary
        state.blink = PLANET_TIME - 1
        state.planet_state = 3
        run_physics_tick(state)
        assert state.planet_state == 4
