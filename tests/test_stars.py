"""Tests for stars.py — PRNG and starfield generation."""

from spacewar.stars import (
    seed_random, random_next, random_x, random_y, generate_stars, STAR_COUNT,
)
from spacewar.constants import VIRTUAL_W, VIRTUAL_H, WRAP_FACTOR


def _rng(b0=0, b1=1, b2=2, b3=3, b4=4, b5=5):
    """Convenience: build a 6-byte RNG state list."""
    return [b0, b1, b2, b3, b4, b5]


class TestRandomNext:
    def test_always_in_range(self):
        rng = _rng(0, 42, 0, 0, 0, 0xA5)
        for _ in range(200):
            val = random_next(rng)
            assert 0 <= val <= 65535

    def test_deterministic_from_same_state(self):
        """Two RNG states initialised identically produce the same sequence."""
        rng1 = _rng(0, 42, 0, 0, 0, 0xA5)
        rng2 = _rng(0, 42, 0, 0, 0, 0xA5)
        seq1 = [random_next(rng1) for _ in range(30)]
        seq2 = [random_next(rng2) for _ in range(30)]
        assert seq1 == seq2

    def test_not_constant(self):
        """PRNG produces more than one distinct value over a run."""
        rng = _rng(0, 1, 2, 3, 4, 5)
        values = {random_next(rng) for _ in range(100)}
        assert len(values) > 1

    def test_modifies_rng_state(self):
        """Each call mutates the state so the next value differs."""
        rng = _rng(0, 1, 2, 3, 4, 5)
        before = rng.copy()
        random_next(rng)
        assert rng != before

    def test_full_16bit_return_value(self):
        """Return value uses both bytes (ax = rng[2]<<8 | rng[0])."""
        # Run many iterations and confirm values > 255 are produced.
        rng = _rng(0, 1, 2, 3, 4, 5)
        high_seen = any(random_next(rng) > 255 for _ in range(200))
        assert high_seen


class TestRandomX:
    def test_always_within_safe_bounds(self):
        rng = _rng(0, 1, 2, 3, 4, 5)
        for _ in range(300):
            val = random_x(rng)
            assert WRAP_FACTOR <= val < VIRTUAL_W - WRAP_FACTOR


class TestRandomY:
    def test_always_within_safe_bounds(self):
        rng = _rng(0, 1, 2, 3, 4, 5)
        for _ in range(300):
            val = random_y(rng)
            assert WRAP_FACTOR <= val < VIRTUAL_H - WRAP_FACTOR


class TestSeedRandom:
    def test_produces_nonzero_state(self):
        """seed_random must leave at least one non-zero byte."""
        rng = [0] * 6
        seed_random(rng)
        assert any(b != 0 for b in rng)

    def test_state_length_preserved(self):
        rng = [0] * 6
        seed_random(rng)
        assert len(rng) == 6

    def test_seeded_rng_produces_valid_output(self):
        """A seeded RNG must produce in-range values immediately."""
        rng = [0] * 6
        seed_random(rng)
        for _ in range(20):
            assert 0 <= random_next(rng) <= 65535


class TestGenerateStars:
    def test_correct_count(self):
        rng = _rng(0, 1, 2, 3, 4, 5)
        stars = generate_stars(rng)
        assert len(stars) == STAR_COUNT

    def test_all_positions_in_bounds(self):
        rng = _rng(0, 1, 2, 3, 4, 5)
        stars = generate_stars(rng)
        for x, y in stars:
            assert WRAP_FACTOR <= x < VIRTUAL_W - WRAP_FACTOR
            assert WRAP_FACTOR <= y < VIRTUAL_H - WRAP_FACTOR

    def test_returns_two_tuples(self):
        rng = _rng(0, 1, 2, 3, 4, 5)
        stars = generate_stars(rng)
        for item in stars:
            assert len(item) == 2

    def test_deterministic_from_same_state(self):
        rng1 = _rng(0, 42, 0, 0, 0, 0xA5)
        rng2 = _rng(0, 42, 0, 0, 0, 0xA5)
        assert generate_stars(rng1) == generate_stars(rng2)

    def test_not_all_same_position(self):
        """512 stars should not all be at the same coordinate."""
        rng = _rng(0, 1, 2, 3, 4, 5)
        stars = generate_stars(rng)
        unique = set(stars)
        assert len(unique) > 1
