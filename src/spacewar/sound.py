"""sound.py — sound synthesis and priority dispatch.

Mirrors SOUND.ASM.

The original uses the PC speaker with Intel 8253 timer chip (port 42H/43H) in
mode-3 square-wave output.  Frequency = 1,193,180 Hz / divisor.

All sounds are square waves (or square-wave sweeps) matching the ASM calculations:

  HYPER_SOUND   — descending sweep: divisor = (flag_counter * 256)
                  → 4661 Hz (flag=1) to 73 Hz (flag=64) over 64 frames ≈ 0.88 s
  PHASER_SOUND  — ascending sweep: neg(STATE) << 3 divisor, PHASER_SOUND_RAMP=8
                  → 601 Hz (step 1) to 1097 Hz (step 15) over ~205 ms
  PHOTON_SOUND  — HI_BLEEP divisor 0x80 = 128 → 9322 Hz, 2 frames ≈ 27 ms
  WARNING_SOUND — alternates HI_PITCH 0x400 (1166 Hz) and LO_PITCH 0x800 (583 Hz)
                  every WARNING_TIME=32 frames ≈ 438 ms per tone
  EXPLOSION_SOUND — random divisor | 0x2000 → 18–145 Hz low rumble, per-frame update
  TORP_HIT_SOUND  — (our addition, no ASM equivalent) short white-noise impact burst

Priority order (highest → lowest, mirrors ASM):
  HYPER_SOUND > PHASER_SOUND > PHOTON_SOUND > WARNING_SOUND

Dedicated channels (bypass priority, always play):
  EXPLOSION_SOUND → channel 3 (force-restart)
  TORP_HIT_SOUND  → channel 2 (play-once)

Public API
----------
init_sound() -> dict[str, pygame.mixer.Sound]
tick_sound(state, sounds)
"""

from __future__ import annotations

import array
import math
import random

import pygame

from .constants import (
    HYPER_SOUND, PHASER_SOUND, PHOTON_SOUND, WARNING_SOUND, EXPLOSION_SOUND,
    TORP_HIT_SOUND,
    WARNING_TIME,
)
from .init import GameState

# Mixer parameters — match a common low-latency config
_SAMPLE_RATE = 22050
_CHANNELS = 1
_SAMPLE_SIZE = -16      # signed 16-bit

# PC speaker clock (Intel 8253 standard)
_PC_CLOCK = 1_193_180

# ---------------------------------------------------------------------------
# Sound generators
# ---------------------------------------------------------------------------

def _gen_square(freq: float, duration_s: float, volume: float = 0.5) -> pygame.mixer.Sound:
    """Generate a fixed-frequency square wave.

    Mirrors the constant-frequency speaker output used for photon and warning
    tones in SOUND.ASM.
    """
    num_samples = int(_SAMPLE_RATE * duration_s)
    amp = int(32767 * volume)
    period = _SAMPLE_RATE / freq if freq > 0 else num_samples
    samples = array.array('h', [
        amp if int(i / period * 2) % 2 == 0 else -amp
        for i in range(num_samples)
    ])
    return pygame.mixer.Sound(buffer=samples)


def _gen_chirp(
    f_start: float,
    f_end: float,
    duration_s: float,
    volume: float = 0.5,
) -> pygame.mixer.Sound:
    """Generate a square-wave frequency sweep (chirp).

    Used for phaser (ascending: ~601→1097 Hz) and hyperspace (descending:
    ~4661→73 Hz).  Mirrors the per-frame timer divisor updates in SOUND.ASM.
    """
    num_samples = int(_SAMPLE_RATE * duration_s)
    amp = int(32767 * volume)
    samples = array.array('h', [0] * num_samples)
    phase = 0.0
    for i in range(num_samples):
        t = i / _SAMPLE_RATE
        freq = f_start + (f_end - f_start) * (t / duration_s)
        phase += 2 * math.pi * freq / _SAMPLE_RATE
        samples[i] = amp if math.sin(phase) >= 0 else -amp
    return pygame.mixer.Sound(buffer=samples)


def _gen_low_rumble(duration_s: float, volume: float = 0.5) -> pygame.mixer.Sound:
    """Generate low-frequency random noise matching SOUND.ASM's EXPLOSION_SOUND.

    ASM: each frame calls Random(), ORs with 0x2000 (8192), writes as divisor.
    Divisor range: 0x2000 (8192) to 0xFFFF (65535)
    → frequency range: 1,193,180/65535 ≈ 18 Hz  to  1,193,180/8192 ≈ 145 Hz

    This is a low, growling rumble — NOT white noise.  The frequency is
    updated every ~13.7 ms (one game frame at 73 Hz).
    """
    num_samples = int(_SAMPLE_RATE * duration_s)
    amp = int(32767 * volume)
    samples = array.array('h', [0] * num_samples)
    samples_per_frame = max(1, int(_SAMPLE_RATE / 73))
    phase = 0.0
    freq = 80.0   # initial arbitrary mid-range value
    for i in range(num_samples):
        if i % samples_per_frame == 0:
            divisor = random.randint(0x2000, 0xFFFF)
            freq = _PC_CLOCK / divisor   # 18–145 Hz
        phase += 2 * math.pi * freq / _SAMPLE_RATE
        samples[i] = amp if math.sin(phase) >= 0 else -amp
    return pygame.mixer.Sound(buffer=samples)


def _gen_noise(duration_s: float, volume: float = 0.4) -> pygame.mixer.Sound:
    """Generate white noise (for torp_hit — no ASM equivalent)."""
    num_samples = int(_SAMPLE_RATE * duration_s)
    amp = int(32767 * volume)
    samples = array.array('h', [random.randint(-amp, amp) for _ in range(num_samples)])
    return pygame.mixer.Sound(buffer=samples)


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------

def init_sound() -> dict[str, pygame.mixer.Sound]:
    """Initialise pygame mixer and create sound buffers.

    Returns a dict of sound objects keyed by name.
    Returns an empty dict if audio init fails (graceful degradation).

    Frequencies derived from SOUND.ASM constants:
      HI_BLEEP  = 0x080  (128)  → 9322 Hz   (photon)
      HI_PITCH  = 0x400 (1024)  → 1166 Hz   (warning high)
      LO_PITCH  = 0x800 (2048)  →  583 Hz   (warning low)
      Phaser: neg(STATE) << 3, STATE steps 8..120 → divisors 1984..1088
              → 601..1097 Hz ascending over 15 frames ≈ 205 ms
      Hyper:  (flag_counter * 256) divisor, counter 1..64
              → 4661..73 Hz descending over 64 frames ≈ 877 ms
    """
    try:
        pygame.mixer.init(frequency=_SAMPLE_RATE, size=_SAMPLE_SIZE, channels=_CHANNELS)
        pygame.mixer.set_num_channels(8)
    except pygame.error:
        return {}

    # Phaser: ascending sweep — 250 Hz (start) → 500 Hz (end) over ~205 ms
    # (Original ASM: 601→1097 Hz; lowered further for preferred tone)
    phaser = _gen_chirp(250, 500, 0.21, 0.5)

    # Photon: sharp blip — 2500 Hz for 27 ms
    # (Original ASM: 9322 Hz; lowered further for less harsh sound)
    photon = _gen_square(2500, 0.03, 0.5)

    # Warning: alternating 500 Hz (hi) and 250 Hz (lo), each for one 32-frame slot
    # (Original ASM: 1166 Hz / 583 Hz; lowered further)
    warning_dur = WARNING_TIME / 73
    warning_hi = _gen_square(500, warning_dur, 0.35)
    warning_lo = _gen_square(250, warning_dur, 0.35)

    # Explosion: random divisor | 0x2000 → 18–145 Hz rumble; duration = SHIP_EXPLOSION_TICKS
    # 100 ticks / 73 fps ≈ 1.37 s
    explosion = _gen_low_rumble(1.38, 0.55)

    # Torp hit: short white-noise burst (no ASM equivalent — our addition)
    torp_hit = _gen_noise(0.10, 0.5)

    # Hyper: descending sweep — 1200 Hz (start) → 40 Hz (end) over ~0.88 s
    # (Original ASM: 4661→73 Hz; lowered further for less piercing onset)
    hyper = _gen_chirp(1200, 40, 0.88, 0.4)

    return {
        'phaser':      phaser,
        'photon':      photon,
        'warning_hi':  warning_hi,
        'warning_lo':  warning_lo,
        'explosion':   explosion,
        'torp_hit':    torp_hit,
        'hyper':       hyper,
    }


# ---------------------------------------------------------------------------
# Per-frame dispatch
# ---------------------------------------------------------------------------

def tick_sound(state: GameState, sounds: dict[str, pygame.mixer.Sound]) -> None:
    """Dispatch sounds based on sound_flag priority.

    Mirrors the SOUND.ASM priority chain.
    Called once per frame from main.py after physics tick.

    Dedicated channels (play unconditionally, not subject to priority masking):
      EXPLOSION_SOUND → channel 3 (force-restart — ship death always audible)
      TORP_HIT_SOUND  → channel 2 (play-once — short impact burst)

    Priority chain (highest → lowest, only one plays per frame):
      HYPER_SOUND > PHASER_SOUND > PHOTON_SOUND > WARNING_SOUND
    """
    if not state.sound_enable or not sounds:
        return

    flag = state.sound_flag

    # Dedicated channels — always play when flagged, regardless of other sounds
    if flag & EXPLOSION_SOUND:
        _play_force(sounds, 'explosion', 3)   # force-restart: ship death must be heard
        state.sound_flag &= ~EXPLOSION_SOUND
    if flag & TORP_HIT_SOUND:
        _play_once(sounds, 'torp_hit', 2)
        state.sound_flag &= ~TORP_HIT_SOUND

    # Priority chain for continuous/competing sounds (mirrors SOUND.ASM if-else chain)
    if flag & HYPER_SOUND:
        _play_once(sounds, 'hyper', 6)
    elif flag & PHASER_SOUND:
        _play_once(sounds, 'phaser', 4)
    elif flag & PHOTON_SOUND:
        _play_once(sounds, 'photon', 5)
        state.sound_flag &= ~PHOTON_SOUND
    elif flag & WARNING_SOUND:
        # Alternate between hi/lo warning tones every WARNING_TIME frames.
        # Mirrors SOUND.ASM: blink & WARNING_TIME == 0 → HI_PITCH, else LO_PITCH.
        name = 'warning_hi' if not (state.blink & WARNING_TIME) else 'warning_lo'
        _play_once(sounds, name, 7)

    # Clear transient phaser/hyper flags after one frame
    state.sound_flag &= ~PHASER_SOUND
    state.sound_flag &= ~HYPER_SOUND


# ---------------------------------------------------------------------------
# Channel helpers
# ---------------------------------------------------------------------------

def _play_once(sounds: dict[str, pygame.mixer.Sound], name: str, channel: int) -> None:
    """Play sound on dedicated channel if not already playing."""
    ch = pygame.mixer.Channel(channel)
    if not ch.get_busy():
        try:
            ch.play(sounds[name])
        except (KeyError, pygame.error):
            pass


def _play_force(sounds: dict[str, pygame.mixer.Sound], name: str, channel: int) -> None:
    """Force-play sound on dedicated channel, restarting if already playing.

    Used for one-shot events (ship death) that must always be audible.
    """
    ch = pygame.mixer.Channel(channel)
    try:
        ch.play(sounds[name])
    except (KeyError, pygame.error):
        pass
