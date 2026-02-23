"""sound.py — sound synthesis and priority dispatch.

Mirrors SOUND.ASM.

The original uses the PC speaker with frequency-modulated square waves.
Here we synthesise approximate equivalents using pygame.mixer.

Priority order (highest → lowest, mirrors ASM):
  HYPER_SOUND > PHASER_SOUND > PHOTON_SOUND > WARNING_SOUND > EXPLOSION_SOUND

All sounds marked  # STUB: approximate  — pitch/timbre to be refined later.

Public API
----------
init_sound() -> dict[str, pygame.mixer.Sound]
tick_sound(state, sounds)
"""

from __future__ import annotations

import array
import math

import pygame

from .constants import (
    HYPER_SOUND, PHASER_SOUND, PHOTON_SOUND, WARNING_SOUND, EXPLOSION_SOUND,
    TARGET_FPS,
)
from .init import GameState

# Mixer parameters
_SAMPLE_RATE = 22050
_CHANNELS = 1
_SAMPLE_SIZE = -16      # signed 16-bit


def _gen_tone(freq: float, duration_s: float, volume: float = 0.5) -> pygame.mixer.Sound:
    """Generate a simple square-wave tone.  # STUB: approximate"""
    num_samples = int(_SAMPLE_RATE * duration_s)
    period = int(_SAMPLE_RATE / freq) if freq > 0 else num_samples
    amp = int(32767 * volume)
    samples = array.array('h', [
        amp if (i // (period // 2 or 1)) % 2 == 0 else -amp
        for i in range(num_samples)
    ])
    sound = pygame.mixer.Sound(buffer=samples)
    return sound


def _gen_noise(duration_s: float, volume: float = 0.4) -> pygame.mixer.Sound:
    """Generate white noise.  # STUB: approximate"""
    import random
    num_samples = int(_SAMPLE_RATE * duration_s)
    amp = int(32767 * volume)
    samples = array.array('h', [random.randint(-amp, amp) for _ in range(num_samples)])
    sound = pygame.mixer.Sound(buffer=samples)
    return sound


def init_sound() -> dict[str, pygame.mixer.Sound]:
    """Initialise pygame mixer and create sound buffers.

    Returns a dict of sound objects keyed by name.
    Returns an empty dict if audio init fails (graceful degradation).
    """
    try:
        pygame.mixer.init(frequency=_SAMPLE_RATE, size=_SAMPLE_SIZE, channels=_CHANNELS)
        pygame.mixer.set_num_channels(8)
    except pygame.error:
        return {}

    return {
        'warning':   _gen_tone(220.0, 0.15, 0.3),    # low warning beep  # STUB
        'phaser':    _gen_tone(800.0, 0.08, 0.5),    # high-pitched zap  # STUB
        'photon':    _gen_tone(440.0, 0.12, 0.5),    # mid torpedo whoosh # STUB
        'explosion': _gen_noise(0.30, 0.6),           # noise burst       # STUB
        'hyper':     _gen_tone(150.0, 0.40, 0.4),    # low rumble        # STUB
    }


def tick_sound(state: GameState, sounds: dict[str, pygame.mixer.Sound]) -> None:
    """Dispatch sounds based on sound_flag priority.

    Mirrors the SOUND.ASM priority chain.
    Called once per frame from main.py after physics tick.
    """
    if not state.sound_enable or not sounds:
        return

    flag = state.sound_flag

    # Priority: highest first
    if flag & HYPER_SOUND:
        _play_once(sounds, 'hyper', 6)
    elif flag & PHASER_SOUND:
        _play_once(sounds, 'phaser', 4)
    elif flag & PHOTON_SOUND:
        _play_once(sounds, 'photon', 5)
        state.sound_flag &= ~PHOTON_SOUND   # one-shot; clear after playing
    elif flag & WARNING_SOUND:
        _play_once(sounds, 'warning', 7)
    elif flag & EXPLOSION_SOUND:
        _play_once(sounds, 'explosion', 3)
        state.sound_flag &= ~EXPLOSION_SOUND

    # Clear transient phaser/hyper flags after one frame
    state.sound_flag &= ~PHASER_SOUND
    state.sound_flag &= ~HYPER_SOUND


def _play_once(sounds: dict[str, pygame.mixer.Sound], name: str, channel: int) -> None:
    """Play sound on dedicated channel if not already playing."""
    ch = pygame.mixer.Channel(channel)
    if not ch.get_busy():
        try:
            ch.play(sounds[name])
        except (KeyError, pygame.error):
            pass
