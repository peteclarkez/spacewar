"""
Shared pytest fixtures and headless Pygame initialisation.

SDL_VIDEODRIVER=dummy and SDL_AUDIODRIVER=dummy ensure tests run in CI
without a physical display or sound card.
"""

import os
import pytest

# Force headless SDL before any pygame import
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


@pytest.fixture(scope="session", autouse=True)
def pygame_headless():
    """Initialise pygame once for the entire test session."""
    import pygame
    pygame.init()
    pygame.display.set_mode((640, 480))   # required for Surface operations
    yield
    pygame.quit()


@pytest.fixture()
def ent_ship():
    """Fresh Enterprise ship at default starting position."""
    from spacewar.ship import Ship
    return Ship.enterprise()


@pytest.fixture()
def kln_ship():
    """Fresh Klingon ship at default starting position."""
    from spacewar.ship import Ship
    return Ship.klingon()


@pytest.fixture()
def ent_torps():
    from spacewar.torpedo import TorpedoPool
    from spacewar.constants import PLAYER_ENT
    return TorpedoPool(PLAYER_ENT)


@pytest.fixture()
def kln_torps():
    from spacewar.torpedo import TorpedoPool
    from spacewar.constants import PLAYER_KLN
    return TorpedoPool(PLAYER_KLN)
