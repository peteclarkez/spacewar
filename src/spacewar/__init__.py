"""
spacewar — faithful Python/Pygame recreation of SpaceWar 1985 (DOS/CGA).

Public API surface for library / test use:

    from spacewar.constants import *
    from spacewar.ship      import Ship
    from spacewar.torpedo   import Torpedo, TorpedoPool
    from spacewar.phaser    import Phaser, cast_phaser
    from spacewar.physics   import wrap, cap_velocity, gravity_delta, distance
    from spacewar.trig      import sin_fp, cos_fp, angle_between
    from spacewar.robot     import left_robot_tick, right_robot_tick
"""

__version__ = "1.0.0"
__all__ = [
    "constants", "trig", "physics", "sprites",
    "ship", "torpedo", "phaser", "planet", "starfield",
    "robot", "audio", "ui", "attract", "joystick", "game",
]
