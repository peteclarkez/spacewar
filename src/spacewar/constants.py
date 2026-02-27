"""
All verified numeric constants for the SpaceWar 1985 faithful recreation.
Values derived from the original DOS/CGA assembly source and game manual.
"""

# ── Display ──────────────────────────────────────────────────────────────────
VIRTUAL_W = 640          # CGA native width (virtual game coord space)
VIRTUAL_H = 200          # CGA native height (virtual game coord space)
DISPLAY_W = 640          # Rendered canvas width
DISPLAY_H = 480          # Rendered canvas height (VIRTUAL_H × Y_SCALE)
Y_SCALE   = 2            # Every virtual Y unit is 2 screen pixels tall
TARGET_FPS = 73          # ~72.8 Hz (1,193,180 / 16390 system interrupts/s)

# ── Screen wrapping ───────────────────────────────────────────────────────────
WRAP_FACTOR = 8          # Objects re-appear WRAP_FACTOR px in from opposite edge

# ── Physics / fixed-point scaling ────────────────────────────────────────────
FRAC          = 65536    # 16.16 fixed-point denominator
MAX_VELOCITY  = 8        # Integer velocity cap per axis (px/tick)
ACCEL_SCALE   = 3        # Thrust right-shift (divides trig value by 8)
FIRE_SCALE    = 2        # Torpedo initial speed left-shift (×4 from ship velocity)

# ── Starfield ─────────────────────────────────────────────────────────────────
STAR_COUNT    = 512      # Static single-pixel stars (drawn in virtual space)

# ── Planet ────────────────────────────────────────────────────────────────────
PLANET_X      = 319      # Planet centre X in virtual coords (640//2 - 1)
PLANET_Y      = 99       # Planet centre Y in virtual coords (200//2 - 1)
PLANET_RANGE  = 16       # Collision radius (virtual pixels)
PLANET_TIME   = 16       # Ticks between planet animation frames
PLANET_FRAMES = 16       # Number of planet animation states
# Rendered size in screen pixels: 48 wide (3:2 from 32-px source), 64 tall (32×Y_SCALE)
PLANET_DRAW_W = 48
PLANET_DRAW_H = 64

# ── Rotation ──────────────────────────────────────────────────────────────────
ANGLE_UNITS   = 256      # Full circle = 256 angle units
ROTATE_RATE   = 2        # Angle units changed per tick while rotate key held

# ── Ship starting state ───────────────────────────────────────────────────────
ENT_START_X   = 160      # Enterprise spawn X (virtual)
ENT_START_Y   = 46       # Enterprise spawn Y (virtual) — ~VIRTUAL_H/4
ENT_START_A   = 0        # Enterprise start angle (facing East)
KLN_START_X   = 480      # Klingon spawn X (virtual)
KLN_START_Y   = 138      # Klingon spawn Y (virtual) — ~3*VIRTUAL_H/4
KLN_START_A   = 128      # Klingon start angle (facing West)

# ── Energy ────────────────────────────────────────────────────────────────────
STARTING_SHIELDS  = 31   # Shield (S) energy per ship at game start
STARTING_ENERGY   = 127  # General (E) / Dilithium energy per ship at start
MAX_ENERGY        = 127  # Unsigned-byte ceiling: recharge stops here
DILITHIUM_TIME    = 256  # Ticks between +1 E-energy recharge
IMPULSE_TIME      = 32   # Ticks between 1 E-unit cost for thrust
CLOAK_TIME        = 32   # Ticks between 1 E-unit cost for cloak
SWAP_TIME         = 4    # Ticks between 1-unit S↔E transfer
LOW_SHIELD_LIMIT  = 16   # Shield warning threshold

# ── Energy costs ──────────────────────────────────────────────────────────────
PHOTON_LAUNCH_ENERGY = 1   # E cost per torpedo fired
PHASER_FIRE_ENERGY   = 1   # E cost per phaser shot
HYPERSPACE_ENERGY    = 8   # E cost for hyperspace jump

# ── Torpedoes ─────────────────────────────────────────────────────────────────
MAX_TORPS          = 7    # Max simultaneous torpedoes per ship
PHOTON_ENERGY      = 40   # Initial torpedo "fuel" (lifespan units)
PHOTON_TIME        = 16   # Ticks between -1 torpedo energy drain
PHOTON_DAMAGE      = 4    # Shield damage per torpedo hit
SHIP_TO_TORP_RANGE = 8    # Ship-torpedo collision radius (virtual px)
TORP_TO_TORP_RANGE = 6    # Torp-torp collision radius (virtual px)
# Torpedo spawn offset from ship centre: cos/sin >> 11 (~15 px max)
TORP_SPAWN_SHIFT   = 11

# ── Phasers ───────────────────────────────────────────────────────────────────
PHASER_RANGE        = 96   # Max phaser ray length (virtual pixels)
PHASER_ERASE        = 20   # Tick at which phaser ray is erased
PHASER_DELAY        = 24   # Full cooldown after firing (ticks)
PHASER_TO_OBJ_RANGE = 8    # Phaser hit-check radius (must be power of 2)
PHASER_DAMAGE       = 2    # Shield damage per phaser hit
PHASER_SKIP         = 9    # Dead zone pixels skipped from ship (no self-hit)

# ── Ship collisions ───────────────────────────────────────────────────────────
SHIP_TO_SHIP_RANGE = 16   # Ship-ship collision radius (virtual px)
BOUNCE_FACTOR      = 2    # Pixels pushed apart after ship-ship collision
PLANET_DAMAGE      = 2    # Shield units drained per tick near planet

# ── Hyperspace / Death explosion ─────────────────────────────────────────────
HYPER_DURATION       = 64   # Total ticks for hyperspace animation
HYPER_PHASE          = 32   # Ticks per expand / contract phase
HYPER_PARTICLES      = 32   # Particles per ship (hyperspace + death)
SHIP_EXPLOSION_TICKS = 40   # ship.exps value set on death (~0.55 s at 73 fps)

# ── Audio ─────────────────────────────────────────────────────────────────────
PHASER_SOUND_RAMP = 8      # Phaser pitch increase per tick
WARNING_TIME      = 32     # Warning sound alternation period (ticks)

# ── Robot AI ─────────────────────────────────────────────────────────────────
PROB_IMPULSE = 16     # Thrust probability: 1 / PROB_IMPULSE per tick
PROB_PHOTON  = 8      # Firing probability: 1 / PROB_PHOTON per tick
PROB_HYPER   = 1024   # Hyperspace probability: 1 / PROB_HYPER per tick

# ── Attract mode ──────────────────────────────────────────────────────────────
ATTRACT_SCREEN_COUNT    = 4     # Number of attract screens
ATTRACT_SCREEN_TICKS    = 600   # Ticks per attract screen (~8 s at 73 fps)

# ── Colours ───────────────────────────────────────────────────────────────────
BLACK  = (0,   0,   0)
WHITE  = (255, 255, 255)

# Neon colour palette
NEON_ENT_GLOW  = (0,   220, 255)   # Electric cyan  — Enterprise
NEON_KLN_GLOW  = (255, 120, 0)     # Orange         — Klingon
NEON_ETORP_GLOW= (0,   255, 100)   # Green          — Enterprise torpedoes
NEON_KTORP_GLOW= (255, 50,  50)    # Red            — Klingon torpedoes
NEON_PLANET    = (160, 80,  255)   # Purple         — Planet (colour shift only)
NEON_STAR      = (20,  20,  70)    # Deep blue      — Starfield
NEON_ENT_HYPER = (0,   160, 255)   # Blue           — Enterprise particles
NEON_KLN_HYPER = (255, 80,  0)     # Orange         — Klingon particles

# ── Player indices ────────────────────────────────────────────────────────────
PLAYER_ENT = 0   # Enterprise = Player 1
PLAYER_KLN = 1   # Klingon    = Player 2

# ── Object table indices ──────────────────────────────────────────────────────
OBJ_ENT        = 0          # Index of Enterprise ship in object table
OBJ_ENT_TORPS  = slice(1, 8)   # Enterprise torpedoes 0-6
OBJ_KLN        = 8          # Index of Klingon ship in object table
OBJ_KLN_TORPS  = slice(9, 16)  # Klingon torpedoes 0-6
