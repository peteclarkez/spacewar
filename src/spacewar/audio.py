"""
Audio system — procedural sound effects driven by game events.

Sound priority (highest first):
  1. Hyperspace
  2. Phaser
  3. Photon torpedo fire
  4. Warning (shield low)
  5. Explosion

All sounds are generated at init using numpy arrays if available,
with a simple sine-wave fallback via pygame.sndarray when numpy is absent.
Sound is completely optional — if init fails the rest of the game continues.
"""

from __future__ import annotations
import math
import struct
import array as _array

_SAMPLE_RATE = 22050
_CHANNELS    = 1
_SAMPLE_SIZE = -16    # signed 16-bit

# Priority levels (lower number = higher priority)
PRI_HYPERSPACE = 1
PRI_PHASER     = 2
PRI_PHOTON     = 3
PRI_WARNING    = 4
PRI_EXPLOSION  = 5

_pygame_ok = False
_sounds: dict[str, object] = {}


def _make_tone(freq: float, duration_ms: int, volume: float = 0.5) -> bytes:
    """Generate a raw 16-bit mono sine-wave tone."""
    n_samples = int(_SAMPLE_RATE * duration_ms / 1000)
    buf = _array.array("h", [0] * n_samples)
    amp = int(32767 * volume)
    for i in range(n_samples):
        t = i / _SAMPLE_RATE
        buf[i] = int(amp * math.sin(2 * math.pi * freq * t))
    return buf.tobytes()


def _make_noise(duration_ms: int, volume: float = 0.3) -> bytes:
    """Generate raw random noise (explosion sound)."""
    import random
    n_samples = int(_SAMPLE_RATE * duration_ms / 1000)
    buf = _array.array("h", [0] * n_samples)
    amp = int(32767 * volume)
    for i in range(n_samples):
        buf[i] = random.randint(-amp, amp)
    return buf.tobytes()


def _make_sweep(freq_start: float, freq_end: float, duration_ms: int, volume: float = 0.5) -> bytes:
    """Generate a frequency sweep (phaser rising pitch)."""
    n_samples = int(_SAMPLE_RATE * duration_ms / 1000)
    buf = _array.array("h", [0] * n_samples)
    amp = int(32767 * volume)
    phase = 0.0
    for i in range(n_samples):
        t = i / n_samples
        freq = freq_start + (freq_end - freq_start) * t
        phase += 2 * math.pi * freq / _SAMPLE_RATE
        buf[i] = int(amp * math.sin(phase))
    return buf.tobytes()


def init() -> bool:
    """Initialise pygame.mixer and pre-generate all sound effects."""
    global _pygame_ok
    try:
        import pygame
        if not pygame.get_init():
            pygame.init()
        pygame.mixer.pre_init(_SAMPLE_RATE, _SAMPLE_SIZE, _CHANNELS, 512)
        pygame.mixer.init()
        _pygame_ok = True
        _build_sounds()
        return True
    except Exception:
        _pygame_ok = False
        return False


def _build_sounds() -> None:
    """Pre-generate Sound objects for all effects."""
    import pygame
    global _sounds

    def _snd(raw: bytes) -> pygame.mixer.Sound:
        return pygame.mixer.Sound(buffer=raw)

    _sounds = {
        "phaser":    _snd(_make_sweep(400, 1800, 300)),
        "photon":    _snd(_make_tone(880, 80)),
        "warning_hi": _snd(_make_tone(660, 200)),
        "warning_lo": _snd(_make_tone(330, 200)),
        "explosion": _snd(_make_noise(400)),
        "hyperspace": _snd(_make_sweep(200, 50, 880)),
    }
    for snd in _sounds.values():
        snd.set_volume(0.5)


class AudioState:
    """
    Tracks which sounds are playing and applies priority logic.
    Updated every game tick via `update()`.
    """

    def __init__(self) -> None:
        self.enabled    = True
        self._priority  = 99
        self._warning_tick = 0
        self._warning_hi   = True
        self._channel: object = None

    def play(self, name: str, priority: int) -> None:
        if not (self.enabled and _pygame_ok):
            return
        if priority <= self._priority:
            self._stop()
            snd = _sounds.get(name)
            if snd:
                import pygame
                self._channel = snd.play()
                self._priority = priority

    def _stop(self) -> None:
        if _pygame_ok:
            import pygame
            pygame.mixer.stop()
        self._priority = 99

    def toggle(self) -> None:
        self.enabled = not self.enabled
        if not self.enabled:
            self._stop()

    def on_phaser(self) -> None:
        self.play("phaser", PRI_PHASER)

    def on_photon(self) -> None:
        self.play("photon", PRI_PHOTON)

    def on_explosion(self) -> None:
        self.play("explosion", PRI_EXPLOSION)

    def on_hyperspace(self) -> None:
        self.play("hyperspace", PRI_HYPERSPACE)

    def update_warning(self, warning_active: bool, tick: int) -> None:
        """Alternate warning tone every WARNING_TIME ticks."""
        from spacewar.constants import WARNING_TIME
        if not warning_active:
            return
        if tick % WARNING_TIME == 0:
            self._warning_hi = not self._warning_hi
            name = "warning_hi" if self._warning_hi else "warning_lo"
            self.play(name, PRI_WARNING)
