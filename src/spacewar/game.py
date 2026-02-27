"""
Main game state machine and loop.

Modes:
  ATTRACT — attract screens cycle; robots may fight
  PLAY    — live gameplay
  PAUSED  — game loop frozen

All collision detection, input dispatching, and rendering happen here.
"""

from __future__ import annotations
import math
import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable

import pygame

from spacewar.constants import (
    DISPLAY_W, DISPLAY_H, TARGET_FPS, BLACK, WHITE, Y_SCALE,
    PLANET_X, PLANET_Y, PLANET_RANGE, PLANET_DAMAGE,
    SHIP_TO_SHIP_RANGE, SHIP_TO_TORP_RANGE, TORP_TO_TORP_RANGE,
    BOUNCE_FACTOR, PHOTON_DAMAGE, PHASER_DAMAGE,
    HYPER_DURATION, HYPER_PHASE, SHIP_EXPLOSION_TICKS,
    VIRTUAL_W, VIRTUAL_H,
    PLAYER_ENT, PLAYER_KLN,
)
from spacewar.ship import Ship
from spacewar.torpedo import TorpedoPool
from spacewar.phaser import Phaser, cast_phaser, draw_phaser
from spacewar.planet import Planet
from spacewar.starfield import Starfield
from spacewar.physics import distance
from spacewar import sprites as SP
from spacewar import robot as ROB
from spacewar.attract import AttractMode
from spacewar.ui import draw_energy_bars, draw_footer, draw_scores
from spacewar.audio import AudioState, init as audio_init
from spacewar.joystick import JoystickManager


class Mode(Enum):
    ATTRACT = auto()
    PLAY    = auto()


@dataclass
class GameState:
    """Global toggles read by the UI footer renderer."""
    robot_ent:  bool = False
    robot_kln:  bool = False
    planet_on:  bool = True
    gravity_on: bool = True
    paused:     bool = False
    sound_on:   bool = True


class Game:
    """Top-level game object. Create once, then call run()."""

    def __init__(self, scale: int = 1, neon: bool = False, altkeys: bool = False) -> None:
        self._scale   = scale
        self._neon    = neon
        self._altkeys = altkeys

        # Game objects
        self.ent   = Ship.enterprise()
        self.kln   = Ship.klingon()
        self.ent_torps = TorpedoPool(PLAYER_ENT)
        self.kln_torps = TorpedoPool(PLAYER_KLN)
        self.ent_phaser = Phaser(owner=PLAYER_ENT)
        self.kln_phaser = Phaser(owner=PLAYER_KLN)

        self.planet    = Planet()
        self.starfield = Starfield()
        self.state     = GameState()
        self.attract   = AttractMode()
        self.audio     = AudioState()
        self.joystick  = JoystickManager()

        self.mode: Mode = Mode.ATTRACT
        self.tick: int  = 0

        # Scores persist across games
        self.ent_score: int = 0
        self.kln_score: int = 0

        # Surfaces
        self._canvas:  pygame.Surface | None = None   # 640×480 logical surface
        self._screen:  pygame.Surface | None = None   # actual window surface
        self._clock:   pygame.time.Clock | None = None

    # ── Pygame init ───────────────────────────────────────────────────────────

    def init_display(self) -> None:
        pygame.init()
        w = DISPLAY_W * self._scale
        h = DISPLAY_H * self._scale
        flags = pygame.RESIZABLE
        self._screen = pygame.display.set_mode((w, h), flags)
        pygame.display.set_caption("SpaceWar 1985")
        self._canvas = pygame.Surface((DISPLAY_W, DISPLAY_H))
        self._clock  = pygame.time.Clock()
        SP.build_sprites(self._neon)
        self.joystick.init()
        audio_init()
        if not self.state.sound_on:
            self.audio.enabled = False

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self) -> None:
        self.init_display()
        running = True
        while running:
            running = self._process_events()
            if not self.state.paused:
                self._update()
            self._render()
            self._flip()
            self._clock.tick(TARGET_FPS)
        pygame.quit()

    # ── Event processing ──────────────────────────────────────────────────────

    def _process_events(self) -> bool:
        """Handle OS events. Returns False to quit."""
        self.joystick.update()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.VIDEORESIZE:
                self._handle_resize(event.w, event.h)
            if event.type == pygame.KEYDOWN:
                if not self._handle_keydown(event.key):
                    return False

        # Joystick edge-triggered inputs
        js0 = self.joystick.states[0]
        js1 = self.joystick.states[1]

        if js0.select_pressed or js1.select_pressed:
            self._enter_attract()
        if (js0.start_pressed or js1.start_pressed):
            if self.mode == Mode.ATTRACT:
                self._start_game()
            else:
                self.state.paused = not self.state.paused
        if js0.rstick_click:
            self.state.robot_ent = not self.state.robot_ent
        if js1.rstick_click:
            self.state.robot_kln = not self.state.robot_kln
        if js0.dpad_up or js1.dpad_up:
            self.state.planet_on = not self.state.planet_on
        if js0.dpad_down or js1.dpad_down:
            self._toggle_sound()

        return True

    def _handle_resize(self, w: int, h: int) -> None:
        self._screen = pygame.display.set_mode((w, h), pygame.RESIZABLE)

    def _handle_keydown(self, key: int) -> bool:
        """Handle function keys and quit. Returns False to quit."""
        if key == pygame.K_ESCAPE:
            return False
        if key == pygame.K_F1:
            self._enter_attract()
        elif key == pygame.K_F2:
            self._start_game()
        elif key == pygame.K_F3:
            self.state.robot_ent = not self.state.robot_ent
        elif key == pygame.K_F4:
            self.state.robot_kln = not self.state.robot_kln
        elif key == pygame.K_F5:
            self.state.planet_on = not self.state.planet_on
        elif key == pygame.K_F6:
            self.state.gravity_on = not self.state.gravity_on
        elif key == pygame.K_F7:
            self.state.paused = not self.state.paused
        elif key == pygame.K_F8:
            self._toggle_sound()
        return True

    def _toggle_sound(self) -> None:
        self.state.sound_on = not self.state.sound_on
        self.audio.toggle()

    # ── Game mode transitions ─────────────────────────────────────────────────

    def _enter_attract(self) -> None:
        self.mode = Mode.ATTRACT

    def _start_game(self) -> None:
        self.ent.reset()
        self.kln.reset()
        self.ent_torps.reset()
        self.kln_torps.reset()
        self.ent_phaser.reset()
        self.kln_phaser.reset()
        self.planet.reset()
        self.mode = Mode.PLAY
        self.tick = 0

    # ── Update ────────────────────────────────────────────────────────────────

    def _update(self) -> None:
        self.tick += 1

        if self.mode == Mode.ATTRACT:
            self.attract.update()
            self.planet.update()
            return

        # ── Play mode ─────────────────────────────────────────────────────────
        keys = pygame.key.get_pressed()
        js0  = self.joystick.states[0]
        js1  = self.joystick.states[1]

        self.planet.update()

        # — Enterprise input —
        if not self.state.robot_ent:
            self._process_ent_input(keys, js0)
        else:
            ROB.left_robot_tick(self.ent, self.kln, self.ent_torps,
                                self.state.gravity_on, self.tick)

        # — Klingon input —
        if not self.state.robot_kln:
            self._process_kln_input(keys, js1)
        else:
            ROB.right_robot_tick(self.kln, self.ent, self.kln_torps,
                                  self.state.gravity_on, self.tick)

        # — Ship physics —
        for ship in (self.ent, self.kln):
            ship.tick_timers()
            ship.tick_energy()
            if ship.alive:
                ship.move(self.state.gravity_on)
            if ship.particles.active:
                ship.particles.update()
                if ship.particles.done and ship.dead:
                    self._enter_attract()

        # — Torpedo physics —
        self.ent_torps.update(self.state.gravity_on, self.tick)
        self.kln_torps.update(self.state.gravity_on, self.tick)

        # — Phaser timers —
        self.ent_phaser.tick()
        self.kln_phaser.tick()

        # — Collisions —
        self._check_collisions()

        # — Audio warnings —
        warn = (self.ent.alive and self.ent.shield_warning) or \
               (self.kln.alive and self.kln.shield_warning)
        self.audio.update_warning(warn, self.tick)

    def _process_ent_input(self, keys, js: object) -> None:
        ship   = self.ent
        torps  = self.ent_torps
        phaser = self.ent_phaser

        thrust   = keys[pygame.K_s]   or js.thrust
        rot_l    = keys[pygame.K_a]   or js.rotate_left
        rot_r    = keys[pygame.K_d]   or js.rotate_right
        cloak    = keys[pygame.K_w]   or js.cloak
        phaser_k = keys[pygame.K_q]   or js.phaser
        torp_k   = keys[pygame.K_e]   or js.torpedo
        hyper_k  = keys[pygame.K_x]   or js.hyperspace
        s2e_k    = keys[pygame.K_z]   or js.shield_to_energy
        e2s_k    = keys[pygame.K_c]   or js.energy_to_shield

        if not ship.alive or ship.particles.active:
            return

        if rot_l:   ship.rotate_left()
        if rot_r:   ship.rotate_right()
        if thrust:  ship.apply_thrust()
        if cloak:   ship.apply_cloak()
        else:       ship.deactivate_cloak()

        if phaser_k and ship.can_fire_phaser():
            self._fire_phaser(ship, phaser)

        if ship.can_fire_torpedo(torp_k):
            ship.consume_torpedo_energy()
            torps.fire(ship.x, ship.y, ship.vx, ship.vy, ship.angle)
            self.audio.on_photon()

        if ship.can_hyperspace(hyper_k):
            self._launch_hyperspace(ship)

        if s2e_k:   ship.shields_to_energy()
        elif e2s_k: ship.energy_to_shields()
        else:       ship.swap_timer = 0

    def _process_kln_input(self, keys, js: object) -> None:
        ship   = self.kln
        torps  = self.kln_torps
        phaser = self.kln_phaser

        if not self._altkeys:
            thrust   = keys[pygame.K_KP5] or js.thrust
            rot_l    = keys[pygame.K_KP4] or js.rotate_left
            rot_r    = keys[pygame.K_KP6] or js.rotate_right
            cloak    = keys[pygame.K_KP8] or js.cloak
            phaser_k = keys[pygame.K_KP7] or js.phaser
            torp_k   = keys[pygame.K_KP9] or js.torpedo
            hyper_k  = keys[pygame.K_KP2] or js.hyperspace
            s2e_k    = keys[pygame.K_KP1] or js.shield_to_energy
            e2s_k    = keys[pygame.K_KP3] or js.energy_to_shield
        else:
            thrust   = keys[pygame.K_k]   or js.thrust
            rot_l    = keys[pygame.K_j]   or js.rotate_left
            rot_r    = keys[pygame.K_l]   or js.rotate_right
            cloak    = keys[pygame.K_i]   or js.cloak
            phaser_k = keys[pygame.K_u]   or js.phaser
            torp_k   = keys[pygame.K_o]   or js.torpedo
            hyper_k  = keys[pygame.K_COMMA] or js.hyperspace
            s2e_k    = keys[pygame.K_m]   or js.shield_to_energy
            e2s_k    = keys[pygame.K_PERIOD] or js.energy_to_shield

        if not ship.alive or ship.particles.active:
            return

        if rot_l:   ship.rotate_left()
        if rot_r:   ship.rotate_right()
        if thrust:  ship.apply_thrust()
        if cloak:   ship.apply_cloak()
        else:       ship.deactivate_cloak()

        if phaser_k and ship.can_fire_phaser():
            self._fire_phaser(ship, phaser)

        if ship.can_fire_torpedo(torp_k):
            ship.consume_torpedo_energy()
            torps.fire(ship.x, ship.y, ship.vx, ship.vy, ship.angle)
            self.audio.on_photon()

        if ship.can_hyperspace(hyper_k):
            self._launch_hyperspace(ship)

        if s2e_k:   ship.shields_to_energy()
        elif e2s_k: ship.energy_to_shields()
        else:       ship.swap_timer = 0

    def _fire_phaser(self, ship: Ship, phaser: Phaser) -> None:
        """Cast phaser ray and apply any hits."""
        ship.fire_phaser()
        phaser.active   = True
        phaser.timer    = ship.phaser_timer   # already set by ship.fire_phaser
        phaser.start_x  = ship.x
        phaser.start_y  = ship.y

        # Determine targets
        if ship.player == PLAYER_ENT:
            target_ships = [self.kln]
            all_torps    = self.kln_torps.active_torpedoes() + \
                           self.ent_torps.active_torpedoes()
        else:
            target_ships = [self.ent]
            all_torps    = self.ent_torps.active_torpedoes() + \
                           self.kln_torps.active_torpedoes()

        ships_hit, torps_hit = cast_phaser(
            phaser, ship.x, ship.y, ship.angle,
            [s for s in target_ships if s.alive and not s.cloaked],
            all_torps,
            self.state.planet_on,
        )

        for hit_ship in ships_hit:
            if hit_ship.apply_damage(PHASER_DAMAGE):
                self._handle_death(hit_ship)

        for t in torps_hit:
            t.begin_explosion()

        self.audio.on_phaser()

    def _launch_hyperspace(self, ship: Ship) -> None:
        ship.consume_hyperspace_energy()
        dest_x = random.uniform(20, VIRTUAL_W - 20)
        dest_y = random.uniform(20, VIRTUAL_H - 20)
        ship.particles.start_hyperspace(ship.x, ship.y, dest_x, dest_y)
        ship.alive = False   # invisible during jump; restored on completion
        self.audio.on_hyperspace()

    def _restore_from_hyperspace(self, ship: Ship) -> None:
        """Called when hyperspace animation completes successfully."""
        ship.x, ship.y = ship.particles.dest_x, ship.particles.dest_y
        ship.vx = ship.vy = 0.0
        ship.alive = True

    def _handle_death(self, ship: Ship) -> None:
        """Trigger death explosion and update scores."""
        ship.dead  = True
        ship.alive = False
        ship.particles.start_death(ship.x, ship.y, ship.vx, ship.vy)
        self.audio.on_explosion()

        if ship.player == PLAYER_ENT:
            self.kln_score += 1
            self.kln.score = self.kln_score
        else:
            self.ent_score += 1
            self.ent.score = self.ent_score

    # ── Collision detection ───────────────────────────────────────────────────

    def _check_collisions(self) -> None:
        # Ship ↔ ship
        self._check_ship_ship()

        # All torp ↔ ship combinations
        all_torp_pools = [(self.ent_torps, PLAYER_ENT),
                          (self.kln_torps, PLAYER_KLN)]
        for pool, owner in all_torp_pools:
            for t in pool.active_torpedoes():
                # Torpedo vs Enterprise
                if self.ent.alive and not self.ent.cloaked:
                    if distance(t.x, t.y, self.ent.x, self.ent.y) < SHIP_TO_TORP_RANGE:
                        t.begin_explosion()
                        if self.ent.apply_damage(PHOTON_DAMAGE):
                            self._handle_death(self.ent)
                # Torpedo vs Klingon
                if self.kln.alive and not self.kln.cloaked:
                    if distance(t.x, t.y, self.kln.x, self.kln.y) < SHIP_TO_TORP_RANGE:
                        t.begin_explosion()
                        if self.kln.apply_damage(PHOTON_DAMAGE):
                            self._handle_death(self.kln)

        # Torp ↔ torp (opposing ships)
        for et in self.ent_torps.active_torpedoes():
            for kt in self.kln_torps.active_torpedoes():
                if distance(et.x, et.y, kt.x, kt.y) < TORP_TO_TORP_RANGE:
                    et.begin_explosion()
                    kt.begin_explosion()

        # Planet hazard
        if self.state.planet_on:
            self._check_planet_hazard()

        # Hyperspace completion check
        for ship in (self.ent, self.kln):
            if ship.particles.active and ship.particles.done:
                if not ship.dead:
                    self._restore_from_hyperspace(ship)

    def _check_ship_ship(self) -> None:
        if not (self.ent.alive and self.kln.alive):
            return
        if distance(self.ent.x, self.ent.y, self.kln.x, self.kln.y) < SHIP_TO_SHIP_RANGE:
            # Inelastic velocity swap
            evx, evy = self.ent.vx, self.ent.vy
            kvx, kvy = self.kln.vx, self.kln.vy
            self.ent.vx, self.ent.vy = kvx * 0.5, kvy * 0.5
            self.kln.vx, self.kln.vy = evx * 0.5, evy * 0.5
            # Push apart
            dx = self.kln.x - self.ent.x
            dy = self.kln.y - self.ent.y
            dist = math.hypot(dx, dy) or 1.0
            nx, ny = dx / dist, dy / dist
            self.ent.x -= nx * BOUNCE_FACTOR
            self.ent.y -= ny * BOUNCE_FACTOR
            self.kln.x += nx * BOUNCE_FACTOR
            self.kln.y += ny * BOUNCE_FACTOR

    def _check_planet_hazard(self) -> None:
        for ship in (self.ent, self.kln):
            if ship.alive and self.planet.contains(ship.x, ship.y):
                if ship.apply_damage(PLANET_DAMAGE):
                    self._handle_death(ship)

        for pool in (self.ent_torps, self.kln_torps):
            for t in pool.active_torpedoes():
                if self.planet.contains(t.x, t.y):
                    t.begin_planet_hit()

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _render(self) -> None:
        canvas = self._canvas
        canvas.fill(BLACK)

        if self.mode == Mode.ATTRACT:
            self.attract.draw(canvas, self.ent_score, self.kln_score,
                              self.planet, self._neon)
        else:
            self._render_play(canvas)

        # Always draw UI overlay
        if self.mode == Mode.PLAY:
            draw_energy_bars(canvas, self.ent, self.kln, self.tick)
            draw_scores(canvas, self.ent_score, self.kln_score)
        draw_footer(canvas, self.state)

    def _render_play(self, canvas: pygame.Surface) -> None:
        self.starfield.draw(canvas, self._neon)

        if self.state.planet_on:
            self.planet.draw(canvas, self._neon)

        # Enterprise
        self._draw_ship(canvas, self.ent)
        # Klingon
        self._draw_ship(canvas, self.kln)

        # Torpedoes
        self.ent_torps.draw(canvas, self._neon)
        self.kln_torps.draw(canvas, self._neon)

        # Phasers
        if self.ent_phaser.active:
            draw_phaser(canvas, self.ent_phaser)
        if self.kln_phaser.active:
            draw_phaser(canvas, self.kln_phaser)

    def _draw_ship(self, canvas: pygame.Surface, ship: Ship) -> None:
        # Draw hyperspace / death particles
        if ship.particles.active:
            colour = (0, 160, 255) if ship.player == PLAYER_ENT else (255, 80, 0)
            ship.particles.draw(canvas, colour, Y_SCALE)

        if not ship.alive or ship.cloaked:
            return

        surf = SP.get_ship_frame(ship.player, ship.angle)
        if self._neon:
            from spacewar.constants import NEON_ENT_GLOW, NEON_KLN_GLOW
            glow = NEON_ENT_GLOW if ship.player == PLAYER_ENT else NEON_KLN_GLOW
            SP.draw_neon_sprite(canvas, surf, ship.x, ship.y, glow)
        else:
            SP.draw_sprite_centered(canvas, surf, ship.x, ship.y)

    # ── Display ───────────────────────────────────────────────────────────────

    def _flip(self) -> None:
        """Scale the 640×480 canvas to the actual window with letterboxing."""
        sw, sh = self._screen.get_size()
        # Compute letterbox rect maintaining 640:480 ratio
        target_ratio = DISPLAY_W / DISPLAY_H
        screen_ratio = sw / sh
        if screen_ratio > target_ratio:
            # Bars on left/right
            bh = sh
            bw = int(sh * target_ratio)
            ox = (sw - bw) // 2
            oy = 0
        else:
            # Bars on top/bottom
            bw = sw
            bh = int(sw / target_ratio)
            ox = 0
            oy = (sh - bh) // 2

        self._screen.fill(BLACK)
        scaled = pygame.transform.scale(self._canvas, (bw, bh))
        self._screen.blit(scaled, (ox, oy))
        pygame.display.flip()
