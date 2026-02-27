"""
Tests for trig.py — 256-unit angle system, lookup tables, and helpers.
"""

import math
import pytest
from spacewar import trig as T


class TestTables:
    def test_table_length(self):
        assert len(T.SIN_TABLE) == 256
        assert len(T.COS_TABLE) == 256

    def test_range(self):
        for v in T.SIN_TABLE:
            assert -32767 <= v <= 32767
        for v in T.COS_TABLE:
            assert -32767 <= v <= 32767

    def test_angle_0_is_east(self):
        # Angle 0 → cos=max, sin≈0
        assert T.COS_TABLE[0] == 32767
        assert T.SIN_TABLE[0] == 0

    def test_angle_64_is_south(self):
        # Angle 64 → cos≈0, sin=max  (screen Y-down)
        assert abs(T.COS_TABLE[64]) <= 1
        assert T.SIN_TABLE[64] == 32767

    def test_angle_128_is_west(self):
        assert T.COS_TABLE[128] == -32767
        assert abs(T.SIN_TABLE[128]) <= 1

    def test_angle_192_is_north(self):
        assert abs(T.COS_TABLE[192]) <= 1
        assert T.SIN_TABLE[192] == -32767

    def test_periodicity(self):
        for i in range(256):
            assert T.SIN_TABLE[i] == T.SIN_TABLE[i % 256]
            assert T.COS_TABLE[i] == T.COS_TABLE[i % 256]


class TestHelpers:
    def test_sin_fp_wraps(self):
        assert T.sin_fp(0)   == T.SIN_TABLE[0]
        assert T.sin_fp(256) == T.SIN_TABLE[0]   # wrap
        assert T.sin_fp(-1)  == T.SIN_TABLE[255]

    def test_cos_fp_wraps(self):
        assert T.cos_fp(0)   == T.COS_TABLE[0]
        assert T.cos_fp(512) == T.COS_TABLE[0]   # 512 & 0xFF = 0

    def test_fp_to_float(self):
        assert T.fp_to_float(32767) == pytest.approx(1.0, abs=1e-4)
        assert T.fp_to_float(0)    == 0.0
        assert T.fp_to_float(-32767) == pytest.approx(-1.0, abs=1e-4)


class TestAngleBetween:
    def test_east(self):
        a = T.angle_between(1, 0)
        assert a == 0

    def test_south(self):
        # dy positive = screen-down = angle 64
        a = T.angle_between(0, 1)
        assert a == 64

    def test_west(self):
        a = T.angle_between(-1, 0)
        assert a == 128

    def test_north(self):
        a = T.angle_between(0, -1)
        assert a == 192

    def test_zero_vector(self):
        assert T.angle_between(0, 0) == 0

    def test_result_range(self):
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                a = T.angle_between(dx, dy)
                assert 0 <= a < 256


class TestThrustComponents:
    def test_thrust_east(self):
        ax, ay = T.thrust_components(0)
        assert ax > 0
        assert abs(ay) < 1e-4

    def test_thrust_west(self):
        ax, ay = T.thrust_components(128)
        assert ax < 0
        assert abs(ay) < 1e-4

    def test_thrust_magnitude(self):
        # Max thrust ≈ (32767 >> 3) / 65536
        ax, _ = T.thrust_components(0)
        expected = (32767 >> 3) / 65536
        assert ax == pytest.approx(expected, rel=1e-3)


class TestTorpedoVelocity:
    def test_forward_boost(self):
        vx, vy = T.torpedo_velocity(0)
        assert vx > 0          # fired eastward
        assert abs(vy) < 1e-4

    def test_magnitude_greater_than_thrust(self):
        # Torpedo adds more velocity than thrust
        tvx, _ = T.torpedo_velocity(0)
        ax,  _ = T.thrust_components(0)
        assert tvx > ax

    def test_fire_scale_2(self):
        # FIRE_SCALE=2 → multiply by 4
        vx, _ = T.torpedo_velocity(0, fire_scale=2)
        # cos(0)=32767; ×4 / 65536 ≈ 2.0
        assert vx == pytest.approx(2.0, abs=0.01)


class TestSpawnOffset:
    def test_east_facing(self):
        ox, oy = T.spawn_offset(0)
        assert ox > 0       # offset is in facing direction
        assert abs(oy) < 1

    def test_offset_larger_than_torp_range(self):
        from spacewar.constants import SHIP_TO_TORP_RANGE
        ox, oy = T.spawn_offset(0)
        # The offset keeps the torpedo outside SHIP_TO_TORP_RANGE
        assert abs(ox) >= SHIP_TO_TORP_RANGE or abs(oy) >= SHIP_TO_TORP_RANGE
