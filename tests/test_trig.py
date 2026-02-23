"""Tests for trig.py — sine/cosine lookup tables and atan approximation."""

import math
import pytest

from spacewar.trig import SINE_TABLE, TAN_TABLE, sin_lookup, cos_lookup, atan_approx


class TestSineTable:
    def test_length(self):
        assert len(SINE_TABLE) == 256

    def test_zero(self):
        assert sin_lookup(0) == 0

    def test_quarter_max(self):
        # sin(64) = peak ≈ 32767
        assert sin_lookup(64) == 0x7FFF

    def test_half(self):
        # sin(128) ≈ 0
        assert sin_lookup(128) == 0

    def test_negative_half(self):
        # sin(192) should be near -32767
        val = sin_lookup(192)
        assert val < 0
        assert val < -32000

    def test_angle_wrap(self):
        # angle 256 should equal angle 0
        assert sin_lookup(256) == sin_lookup(0)
        assert sin_lookup(257) == sin_lookup(1)
        assert sin_lookup(-1) == sin_lookup(255)

    def test_all_in_range(self):
        for i, v in enumerate(SINE_TABLE):
            assert -32768 <= v <= 32767, f"SINE_TABLE[{i}] = {v} out of range"

    def test_symmetry_positive(self):
        # sin(64-k) == sin(64+k) for first quadrant symmetry
        for k in range(1, 32):
            assert sin_lookup(64 - k) == sin_lookup(64 + k), f"Symmetry failed at k={k}"

    def test_first_quarter_increasing(self):
        # Values should increase from 0 to 64
        for i in range(63):
            assert sin_lookup(i) <= sin_lookup(i + 1), f"Not increasing at index {i}"


class TestCosTable:
    def test_cos_is_sin_plus_64(self):
        # cos(x) = sin(x + 64) for all angles
        for a in range(256):
            assert cos_lookup(a) == sin_lookup((a + 64) & 0xFF)

    def test_cos_zero(self):
        # cos(0) = sin(64) = max
        assert cos_lookup(0) == 0x7FFF

    def test_cos_90(self):
        # cos(64) = sin(128) ≈ 0
        assert cos_lookup(64) == 0

    def test_cos_180(self):
        # cos(128) = sin(192) ≈ -32767
        assert cos_lookup(128) < -32000

    def test_cos_270(self):
        # cos(192) = sin(256) = sin(0) = 0
        assert cos_lookup(192) == 0


class TestTanTable:
    def test_length(self):
        assert len(TAN_TABLE) == 32

    def test_first_zero(self):
        assert TAN_TABLE[0] == 0

    def test_all_positive(self):
        for i, v in enumerate(TAN_TABLE):
            assert v >= 0, f"TAN_TABLE[{i}] = {v} should be positive"

    def test_monotone_increasing(self):
        for i in range(31):
            assert TAN_TABLE[i] <= TAN_TABLE[i + 1]


class TestAtanApprox:
    def test_right(self):
        # Pointing right (+x) → angle 0
        assert atan_approx(1, 0) == 0

    def test_down(self):
        # Pointing down (+y in screen coords) → angle 64
        assert atan_approx(0, 1) == 64

    def test_left(self):
        # Pointing left (−x) → angle 128
        assert atan_approx(-1, 0) == 128

    def test_up(self):
        # Pointing up (−y) → angle 192
        assert atan_approx(0, -1) == 192

    def test_zero_input(self):
        # Origin → return 0 (no crash)
        assert atan_approx(0, 0) == 0

    def test_diagonal_down_right(self):
        # 45° down-right → angle 32
        angle = atan_approx(1, 1)
        assert 28 <= angle <= 36, f"Expected ~32, got {angle}"

    def test_result_in_range(self):
        # All results must be in [0, 255]
        for dx in range(-5, 6):
            for dy in range(-5, 6):
                if dx == 0 and dy == 0:
                    continue
                result = atan_approx(dx, dy)
                assert 0 <= result <= 255, f"atan_approx({dx},{dy}) = {result}"
