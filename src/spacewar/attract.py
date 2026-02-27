"""
Attract mode — cycles through 4 screens with animated SPACEWAR title.

Screens (cycled every ATTRACT_SCREEN_TICKS):
  0 — Title + scores
  1 — Game Instructions
  2 — Key Layout
  3 — User-Supported Software

The planet is rendered in the top-right corner during attract mode.
"""

from __future__ import annotations
import math
import random

import pygame

from spacewar.constants import (
    DISPLAY_W, DISPLAY_H, WHITE, BLACK,
    ATTRACT_SCREEN_COUNT, ATTRACT_SCREEN_TICKS,
    PLANET_X, PLANET_Y, Y_SCALE,
)


# ── Letter explosion animation ────────────────────────────────────────────────

_TITLE = "SPACEWAR"

class _LetterParticle:
    __slots__ = ("x", "y", "vx", "vy", "target_x", "target_y", "active")

    def __init__(self):
        self.x = self.y = 0.0
        self.vx = self.vy = 0.0
        self.target_x = self.target_y = 0.0
        self.active = False


class TitleAnimation:
    """
    'SPACEWAR' letters that explode apart and reform in a loop.
    Phase 0 (0–80 ticks):   letters assemble from random positions
    Phase 1 (80–160 ticks): static title display
    Phase 2 (160–240 ticks): letters explode outward
    Total loop: 240 ticks
    """

    LOOP = 240
    ASSEMBLE_END   = 80
    STATIC_END     = 160
    # EXPLODE runs from STATIC_END to LOOP

    def __init__(self) -> None:
        self._tick = 0
        self._particles: list[_LetterParticle] = []
        self._font: pygame.font.Font | None = None
        self._letter_surfs: list[pygame.Surface] = []
        self._letter_w = 0
        self._positions: list[tuple[int, int]] = []   # target screen positions

    def _ensure_font(self) -> None:
        if self._font is None:
            self._font = pygame.font.SysFont("monospace", 48, bold=True)
            self._letter_surfs = [
                self._font.render(ch, True, WHITE) for ch in _TITLE
            ]
            self._letter_w = self._letter_surfs[0].get_width()
            total_w = self._letter_w * len(_TITLE) + 4 * (len(_TITLE) - 1)
            start_x = (DISPLAY_W - total_w) // 2
            target_y = DISPLAY_H // 3
            self._positions = [
                (start_x + i * (self._letter_w + 4), target_y)
                for i in range(len(_TITLE))
            ]
            self._init_particles()

    def _init_particles(self) -> None:
        self._particles = []
        for i, (tx, ty) in enumerate(self._positions):
            p = _LetterParticle()
            p.target_x = float(tx)
            p.target_y = float(ty)
            p.x = random.uniform(0, DISPLAY_W)
            p.y = random.uniform(0, DISPLAY_H // 2)
            p.vx = (p.target_x - p.x) / self.ASSEMBLE_END
            p.vy = (p.target_y - p.y) / self.ASSEMBLE_END
            p.active = True
            self._particles.append(p)

    def update(self) -> None:
        self._tick = (self._tick + 1) % self.LOOP
        t = self._tick

        if not self._particles:
            return

        if t == 0:
            # Restart cycle — reset particles inward
            for p in self._particles:
                p.x = random.uniform(0, DISPLAY_W)
                p.y = random.uniform(0, DISPLAY_H // 2)
                p.vx = (p.target_x - p.x) / self.ASSEMBLE_END
                p.vy = (p.target_y - p.y) / self.ASSEMBLE_END

        if t < self.ASSEMBLE_END:
            # Phase 0: move toward target
            for p in self._particles:
                p.x += p.vx
                p.y += p.vy

        elif t == self.STATIC_END:
            # Phase 2: trigger explosion
            for p in self._particles:
                p.x = p.target_x
                p.y = p.target_y
                angle = random.random() * 2 * math.pi
                speed = random.uniform(2, 6)
                p.vx = math.cos(angle) * speed
                p.vy = math.sin(angle) * speed

        elif t > self.STATIC_END:
            for p in self._particles:
                p.x += p.vx
                p.y += p.vy

    def draw(self, surface: pygame.Surface) -> None:
        if self._font is None:
            self._ensure_font()

        t = self._tick
        if t < self.ASSEMBLE_END or t > self.STATIC_END:
            # Draw letter images at particle positions
            for i, p in enumerate(self._particles):
                surf = self._letter_surfs[i]
                surface.blit(surf, (int(p.x), int(p.y)))
        else:
            # Draw static assembled title
            for i, (tx, ty) in enumerate(self._positions):
                surface.blit(self._letter_surfs[i], (tx, ty))


# ── Attract mode state machine ────────────────────────────────────────────────

class AttractMode:
    """
    Manages all 4 attract screens and the title animation.
    Call update() and draw() every game tick while in attract mode.
    """

    def __init__(self) -> None:
        self._screen_tick: int = 0
        self._screen_idx:  int = 0
        self.title_anim = TitleAnimation()
        self._font_sm: pygame.font.Font | None = None
        self._font_md: pygame.font.Font | None = None

    def _fsm(self) -> pygame.font.Font:
        if self._font_sm is None:
            self._font_sm = pygame.font.SysFont("monospace", 14)
        return self._font_sm

    def _fmd(self) -> pygame.font.Font:
        if self._font_md is None:
            self._font_md = pygame.font.SysFont("monospace", 18, bold=True)
        return self._font_md

    def update(self) -> None:
        self._screen_tick += 1
        if self._screen_tick >= ATTRACT_SCREEN_TICKS:
            self._screen_tick = 0
            self._screen_idx = (self._screen_idx + 1) % ATTRACT_SCREEN_COUNT
        self.title_anim.update()

    def draw(self, surface: pygame.Surface, ent_score: int, kln_score: int,
             planet, neon: bool = False) -> None:
        surface.fill(BLACK)

        # Planet in top-right corner (attract thumbnail)
        attract_planet_x = DISPLAY_W - 60
        attract_planet_y = 30   # screen pixels → virtual: 30//Y_SCALE = 15
        planet.draw(surface, neon=neon,
                    cx=attract_planet_x,
                    cy=attract_planet_y // Y_SCALE,
                    scale_factor=0.5)

        idx = self._screen_idx
        if idx == 0:
            self._draw_title_screen(surface, ent_score, kln_score)
        elif idx == 1:
            self._draw_instructions(surface)
        elif idx == 2:
            self._draw_keys(surface)
        else:
            self._draw_shareware(surface)

    def _draw_title_screen(self, surface, ent_score, kln_score) -> None:
        self.title_anim.draw(surface)
        fnt = self._fmd()
        score_txt = fnt.render(
            f"Enterprise {ent_score}   Klingon {kln_score}", True, WHITE
        )
        surface.blit(score_txt, ((DISPLAY_W - score_txt.get_width()) // 2,
                                  DISPLAY_H * 2 // 3))
        hint = self._fsm().render("Press F2 to Play", True, WHITE)
        surface.blit(hint, ((DISPLAY_W - hint.get_width()) // 2, DISPLAY_H - 60))

    def _draw_instructions(self, surface) -> None:
        lines = [
            "GAME INSTRUCTIONS",
            "",
            "Two ships battle near a gravitational planet.",
            "Each ship has S (Shield) and E (Energy) bars.",
            "",
            "WEAPONS:",
            "  Phasers  — short-range beam; shoots down torpedoes",
            "  Torpedoes — gravity-affected; 7 max per ship",
            "",
            "DEFENCE:",
            "  Cloak     — invisible to both players while held",
            "  Hyperspace — teleport to random location (costs 8E)",
            "",
            "ENERGY RULES:",
            "  Thrust, Cloak, Phasers, Torpedoes all cost E-energy",
            "  Transfer S<->E manually with balance keys",
            "  Shields do NOT recharge; Energy recharges slowly",
        ]
        self._render_lines(surface, lines, start_y=40)

    def _draw_keys(self, surface) -> None:
        lines = [
            "CONTROLS",
            "",
            "Enterprise (P1)    Klingon (P2)",
            "Q  Fire Phasers    7  Fire Phasers",
            "W  Cloak           8  Cloak",
            "E  Fire Torpedo    9  Fire Torpedo",
            "A  Rotate Left     4  Rotate Left",
            "S  Thrust          5  Thrust",
            "D  Rotate Right    6  Rotate Right",
            "Z  Shields->Energy 1  Shields->Energy",
            "X  Hyperspace      2  Hyperspace",
            "C  Energy->Shields 3  Energy->Shields",
            "",
            "F1 Attract  F2 Play  F3 Ent-Robot  F4 Kln-Robot",
            "F5 Planet   F6 Gravity  F7 Pause    F8 Sound",
        ]
        self._render_lines(surface, lines, start_y=30)

    def _draw_shareware(self, surface) -> None:
        lines = [
            "SPACEWAR  1985",
            "",
            "A faithful Python/Pygame recreation",
            "of the classic DOS/CGA game.",
            "",
            "Original game by David Ahl (1985).",
            "",
            "Recreation released as open-source",
            "user-supported software.",
            "",
            "Enjoy — and may your shields hold!",
        ]
        self._render_lines(surface, lines, start_y=80)

    def _render_lines(self, surface, lines, start_y=40) -> None:
        fnt = self._fsm()
        y = start_y
        for line in lines:
            if line:
                txt = fnt.render(line, True, WHITE)
                surface.blit(txt, (20, y))
            y += fnt.get_height() + 2
