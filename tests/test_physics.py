"""
Tests for physics.py — wrap, cap_velocity, gravity, integration, particles.
"""

import math
import pytest
from spacewar.physics import (
    wrap_x, wrap_y, wrap,
    cap_velocity,
    gravity_delta,
    integrate,
    distance,
    ParticleSystem,
)
from spacewar.constants import (
    VIRTUAL_W, VIRTUAL_H, WRAP_FACTOR,
    MAX_VELOCITY, FRAC,
    PLANET_X, PLANET_Y,
    HYPER_DURATION, HYPER_PHASE, HYPER_PARTICLES,
)


class TestWrap:
    def test_no_wrap_in_centre(self):
        x, y = wrap(320.0, 100.0)
        assert x == 320.0
        assert y == 100.0

    def test_wrap_left_edge(self):
        x = wrap_x(WRAP_FACTOR - 1.0)
        assert x > VIRTUAL_W // 2     # jumped to right side

    def test_wrap_right_edge(self):
        x = wrap_x(float(VIRTUAL_W - WRAP_FACTOR))
        assert x < VIRTUAL_W // 2     # jumped to left side

    def test_wrap_top_edge(self):
        y = wrap_y(WRAP_FACTOR - 1.0)
        assert y > VIRTUAL_H // 2

    def test_wrap_bottom_edge(self):
        y = wrap_y(float(VIRTUAL_H - WRAP_FACTOR))
        assert y < VIRTUAL_H // 2

    def test_wrap_symmetry(self):
        # Going off the right should appear near the left
        x1 = wrap_x(float(VIRTUAL_W - WRAP_FACTOR))
        x2 = wrap_x(float(WRAP_FACTOR - 1))
        # Both should be in the valid range
        assert WRAP_FACTOR <= x1 < VIRTUAL_W - WRAP_FACTOR
        assert WRAP_FACTOR <= x2 < VIRTUAL_W - WRAP_FACTOR


class TestCapVelocity:
    def test_within_range(self):
        assert cap_velocity(4.0) == 4.0
        assert cap_velocity(-4.0) == -4.0
        assert cap_velocity(0.0) == 0.0

    def test_cap_positive(self):
        assert cap_velocity(10.0) == MAX_VELOCITY

    def test_cap_negative(self):
        assert cap_velocity(-10.0) == -MAX_VELOCITY

    def test_exactly_at_cap(self):
        assert cap_velocity(float(MAX_VELOCITY))  == MAX_VELOCITY
        assert cap_velocity(float(-MAX_VELOCITY)) == -MAX_VELOCITY


class TestGravity:
    def test_pulls_toward_centre(self):
        # Object to the right of planet → should be pulled left (negative x)
        ax, ay = gravity_delta(PLANET_X + 100, PLANET_Y)
        assert ax < 0
        assert abs(ay) < 1e-10

    def test_pulls_upward_if_below(self):
        ax, ay = gravity_delta(PLANET_X, PLANET_Y + 50)
        assert ay < 0
        assert abs(ax) < 1e-10

    def test_zero_at_centre(self):
        ax, ay = gravity_delta(PLANET_X, PLANET_Y)
        assert ax == pytest.approx(0.0)
        assert ay == pytest.approx(0.0)

    def test_magnitude_proportional_to_distance(self):
        ax1, _ = gravity_delta(PLANET_X + 10, PLANET_Y)
        ax2, _ = gravity_delta(PLANET_X + 20, PLANET_Y)
        assert abs(ax2) == pytest.approx(abs(ax1) * 2, rel=1e-4)

    def test_formula(self):
        # accel = -(x - PLANET_X) * 8 / FRAC
        ax, ay = gravity_delta(PLANET_X + 50, PLANET_Y + 30)
        assert ax == pytest.approx(-50 * 8 / FRAC)
        assert ay == pytest.approx(-30 * 8 / FRAC)


class TestIntegrate:
    def test_simple_move(self):
        x, y = integrate(100.0, 50.0, 1.0, 2.0)
        assert x == pytest.approx(101.0)
        assert y == pytest.approx(52.0)

    def test_wraps_after_integrate(self):
        # Start near right edge, moving right
        x, y = integrate(float(VIRTUAL_W - WRAP_FACTOR - 0.5), 50.0, 2.0, 0.0)
        assert x < VIRTUAL_W // 2     # has wrapped to left side


class TestDistance:
    def test_zero(self):
        assert distance(0, 0, 0, 0) == 0.0

    def test_horizontal(self):
        assert distance(0, 0, 3, 0) == pytest.approx(3.0)

    def test_vertical(self):
        assert distance(0, 0, 0, 4) == pytest.approx(4.0)

    def test_diagonal(self):
        assert distance(0, 0, 3, 4) == pytest.approx(5.0)

    def test_symmetric(self):
        assert distance(10, 20, 30, 40) == distance(30, 40, 10, 20)


class TestParticleSystem:
    def test_initially_inactive(self):
        ps = ParticleSystem()
        assert not ps.active
        assert not ps.done

    def test_start_death_activates(self):
        ps = ParticleSystem()
        ps.start_death(100.0, 50.0)
        assert ps.active
        assert ps.is_death
        assert all(p.active for p in ps.particles)

    def test_start_hyperspace_activates(self):
        ps = ParticleSystem()
        ps.start_hyperspace(100.0, 50.0, 300.0, 150.0)
        assert ps.active
        assert not ps.is_death
        assert ps.dest_x == 300.0
        assert ps.dest_y == 150.0

    def test_particles_count(self):
        ps = ParticleSystem()
        ps.start_death(100.0, 50.0)
        assert len(ps.particles) == HYPER_PARTICLES

    def test_update_advances_tick(self):
        ps = ParticleSystem()
        ps.start_death(100.0, 50.0)
        ps.update()
        assert ps.tick == 2

    def test_done_after_duration(self):
        ps = ParticleSystem()
        ps.start_hyperspace(100.0, 50.0, 300.0, 150.0)
        for _ in range(HYPER_DURATION + 2):
            ps.update()
        assert ps.done
        assert all(not p.active for p in ps.particles)

    def test_death_particles_spread(self):
        ps = ParticleSystem()
        ps.start_death(320.0, 100.0)
        # After a few updates particles should have spread out
        for _ in range(10):
            ps.update()
        xs = [p.x for p in ps.particles]
        ys = [p.y for p in ps.particles]
        assert max(xs) - min(xs) > 5  # spread across several pixels
        assert max(ys) - min(ys) > 5

    def test_hyperspace_phase_transition(self):
        """At tick HYPER_PHASE+1 particles should converge on destination."""
        ps = ParticleSystem()
        dest_x, dest_y = 400.0, 150.0
        ps.start_hyperspace(100.0, 50.0, dest_x, dest_y)
        # Run through phase 1 plus one tick
        for _ in range(HYPER_PHASE + 1):
            ps.update()
        # After transition all particles should be heading toward dest.
        # Allow 10px tolerance due to random scatter accumulated during phase 1.
        for p in ps.particles:
            if p.active:
                remaining = HYPER_PHASE
                projected_x = p.x + p.vx * remaining
                projected_y = p.y + p.vy * remaining
                assert abs(projected_x - dest_x) < 10
                assert abs(projected_y - dest_y) < 10
