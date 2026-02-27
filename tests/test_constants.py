"""
Tests for constants.py — verify all documented magic numbers are present
and internally consistent.
"""

from spacewar import constants as C


def test_virtual_dimensions():
    assert C.VIRTUAL_W == 640
    assert C.VIRTUAL_H == 200
    assert C.DISPLAY_W == 640
    assert C.DISPLAY_H == 480
    assert C.Y_SCALE   == 2
    # 480 approximates the original CGA aspect; Y_SCALE=2 for rendering rows
    assert C.DISPLAY_H > C.VIRTUAL_H * C.Y_SCALE // 2


def test_wrap_factor():
    assert C.WRAP_FACTOR == 8


def test_velocity():
    assert C.MAX_VELOCITY == 8
    assert C.FRAC == 65536


def test_planet_constants():
    assert C.PLANET_X == 319
    assert C.PLANET_Y == 99
    assert C.PLANET_RANGE == 16
    assert C.PLANET_TIME  == 16
    assert C.PLANET_FRAMES == 16
    # Planet should be roughly centred on the virtual screen
    assert abs(C.PLANET_X - C.VIRTUAL_W // 2) <= 1
    assert abs(C.PLANET_Y - C.VIRTUAL_H // 2) <= 1


def test_starting_energy():
    assert C.STARTING_SHIELDS == 31
    assert C.STARTING_ENERGY  == 127
    assert C.MAX_ENERGY        == 127


def test_energy_costs():
    assert C.HYPERSPACE_ENERGY    == 8
    assert C.PHOTON_LAUNCH_ENERGY == 1
    assert C.PHASER_FIRE_ENERGY   == 1


def test_torpedo_constants():
    assert C.MAX_TORPS          == 7
    assert C.PHOTON_ENERGY      == 40
    assert C.PHOTON_TIME        == 16
    assert C.PHOTON_DAMAGE      == 4
    assert C.SHIP_TO_TORP_RANGE == 8
    assert C.TORP_TO_TORP_RANGE == 6


def test_phaser_constants():
    assert C.PHASER_RANGE        == 96
    assert C.PHASER_ERASE        == 20
    assert C.PHASER_DELAY        == 24
    assert C.PHASER_TO_OBJ_RANGE == 8
    assert C.PHASER_DAMAGE       == 2
    # PHASER_TO_OBJ_RANGE must be a power of two (original requirement)
    r = C.PHASER_TO_OBJ_RANGE
    assert r > 0 and (r & (r - 1)) == 0


def test_collision_constants():
    assert C.SHIP_TO_SHIP_RANGE == 16
    assert C.BOUNCE_FACTOR      == 2
    assert C.PLANET_DAMAGE      == 2


def test_hyperspace_constants():
    assert C.HYPER_DURATION   == 64
    assert C.HYPER_PHASE      == 32
    assert C.HYPER_PARTICLES  == 32
    assert C.HYPER_DURATION   == C.HYPER_PHASE * 2


def test_timing_constants():
    assert C.DILITHIUM_TIME   == 256
    assert C.IMPULSE_TIME     == 32
    assert C.CLOAK_TIME       == 32
    assert C.SWAP_TIME        == 4
    assert C.WARNING_TIME     == 32
    assert C.SHIP_EXPLOSION_TICKS == 40


def test_robot_probabilities():
    assert C.PROB_IMPULSE ==   16
    assert C.PROB_PHOTON  ==    8
    assert C.PROB_HYPER   == 1024


def test_angle_system():
    assert C.ANGLE_UNITS  == 256
    assert C.ROTATE_RATE  ==   2
    assert C.ACCEL_SCALE  ==   3
    assert C.FIRE_SCALE   ==   2


def test_starting_positions():
    assert C.ENT_START_X == 160
    assert C.ENT_START_A ==   0      # Enterprise faces East
    assert C.KLN_START_X == 480
    assert C.KLN_START_A == 128     # Klingon faces West
    # Symmetry: together they span the screen
    assert C.KLN_START_X - C.ENT_START_X == C.VIRTUAL_W // 2


def test_player_indices():
    assert C.PLAYER_ENT == 0
    assert C.PLAYER_KLN == 1
