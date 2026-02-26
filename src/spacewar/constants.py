"""constants.py — all named game constants.

Mirrors GENERAL.EQU, PLANET.EQU, PHASER.EQU, PLAYINT.EQU, SOUND.EQU, KEYS.EQU.
No logic, no imports.  All values verified against v1.50 Assembly source.
"""

# ---------------------------------------------------------------------------
# Display / virtual coordinate space   (GENERAL.EQU)
# ---------------------------------------------------------------------------
VIRTUAL_W: int = 640          # MAX_X_AXIS — virtual pixels wide
VIRTUAL_H: int = 200          # MAX_Y_AXIS — virtual pixels tall
SCREEN_W: int = 640           # Physical window width
SCREEN_H: int = 480           # Physical window height (Y doubled)
Y_SCALE: int = 2              # Each virtual row → 2 screen rows
# Canonical game surface dimensions (the intermediate render target).
# All draw/phaser/attract code bounds-checks against these values, which is
# correct because game_surface is always exactly GAME_W × GAME_H.
GAME_W: int = SCREEN_W        # 640
GAME_H: int = SCREEN_H        # 480

# ---------------------------------------------------------------------------
# Physics                              (GENERAL.EQU / PLAYINT.EQU)
# ---------------------------------------------------------------------------
WRAP_FACTOR: int = 8          # Margin at screen edges before wrap
MAX_X_VEL: int = 8            # MAX_X_VELOCITY — clamp threshold
MAX_Y_VEL: int = 8            # MAX_Y_VELOCITY
ACCEL_SCALE: int = 3          # Thrust acceleration SAR (÷8)
FIRE_SCALE: int = 2           # Torpedo launch speed SAR (÷4) from cos/sin max
ROTATE_RATE: int = 2          # Degrees (in 0-255 space) per tick

# Timing intervals — all powers of 2, gated on BLINK counter
IMPULSE_TIME: int = 32        # Ticks between thrust energy drains
CLOAK_TIME: int = 32          # Ticks between cloak energy drains
DILITHIUM_TIME: int = 256     # Ticks between energy recharge (+1 E)
PHOTON_TIME: int = 16         # Ticks between torpedo energy drains
PLANET_TIME: int = 16         # Ticks between planet animation frames
WARNING_TIME: int = 32        # Ticks between shield warning sound toggling
SWAP_TIME: int = 4            # Ticks between S↔E energy transfer pulses

TARGET_FPS: int = 73          # 1,193,180 / 16,390 ≈ 72.8 Hz

# ---------------------------------------------------------------------------
# Starting positions                   (INIT.ASM / GENERAL.EQU)
# ---------------------------------------------------------------------------
# Enterprise starts at (MAX_X/4, (MAX_Y-16)/4)
ENT_START_X: int = 160        # 640 / 4
ENT_START_Y: int = 46         # (200 - 16) / 4
ENT_START_ANGLE: int = 0      # pointing right

# Klingon starts at (3*MAX_X/4, 3*(MAX_Y-16)/4)
KLN_START_X: int = 480        # 3 * 640 / 4
KLN_START_Y: int = 138        # 3 * (200 - 16) / 4
KLN_START_ANGLE: int = 128    # pointing left (180°)

# ---------------------------------------------------------------------------
# Energy / shields                     (INIT.ASM)
# ---------------------------------------------------------------------------
STARTING_SHIELDS: int = 31    # ZSHLDS — initial shield energy
STARTING_ENERGY: int = 127    # ZENRGY — initial dilithium energy (max)

# ---------------------------------------------------------------------------
# Planet                               (PLANET.EQU)
# ---------------------------------------------------------------------------
PLANET_X: int = 319           # (640/2) - 1
PLANET_Y: int = 99            # (200/2) - 1
ATTRACT_PLANET_X: int = 592   # MAX_X - 3*16 (top-right corner in attract)
ATTRACT_PLANET_Y: int = 24    # top-right corner in attract
PLANET_RANGE: int = 16        # Manhattan collision radius
PLANET_SIZE: int = 16         # Sprite half-width (pixels)

# ---------------------------------------------------------------------------
# Weapons — Phaser                     (PHASER.EQU)
# ---------------------------------------------------------------------------
PHASER_FIRE_ENERGY: int = 1   # Energy cost to fire
PHASER_RANGE: int = 96        # Maximum ray length in virtual pixels
PHASER_DELAY: int = 24        # Cooldown ticks after firing (PHST initial)
PHASER_ERASE: int = 20        # Tick at which the ray is erased
PHASER_TO_OBJ_RANGE: int = 8  # Manhattan hit-check interval along ray
PHASER_DAMAGE: int = 2        # Shield damage per phaser hit

# Phaser state machine sentinel
PHASER_IDLE: int = 255        # ZPHST — phaser not firing

# ---------------------------------------------------------------------------
# Weapons — Torpedo                    (TORP.ASM / GENERAL.EQU)
# ---------------------------------------------------------------------------
PHOTON_LAUNCH_ENERGY: int = 1 # Energy cost to launch one torpedo
PHOTON_ENERGY: int = 40       # Energy given to torpedo at launch (ENRGY)
PHOTON_DAMAGE: int = 4        # Shield damage per torpedo hit
HYPERSPACE_ENERGY: int = 8    # Energy cost to jump

# ---------------------------------------------------------------------------
# Collision ranges                     (CMPS.ASM)
# ---------------------------------------------------------------------------
SHIP_TO_SHIP_RANGE: int = 16  # Manhattan radius for ship-ship collision
SHIP_TO_TORP_RANGE: int = 8   # Manhattan radius for ship-torpedo collision
TORP_TO_TORP_RANGE: int = 6   # Manhattan radius for torp-torp collision
BOUNCE_FACTOR: int = 2        # Pixels ships are pushed apart on ship-ship hit
PLANET_DAMAGE: int = 2        # Shield damage from planet contact

# ---------------------------------------------------------------------------
# Sound flags                          (SOUND.EQU)
# ---------------------------------------------------------------------------
WARNING_SOUND: int = 0x01
PHASER_SOUND: int = 0x02
PHOTON_SOUND: int = 0x04
EXPLOSION_SOUND: int = 0x08
HYPER_SOUND: int = 0x10
PHASER_SOUND_RAMP: int = 8    # Phaser pitch step counter max
LOW_SHIELD_LIMIT: int = 16    # Below this → warning sound activates

# ---------------------------------------------------------------------------
# Robot AI probabilities               (MAIN.ASM)
# ---------------------------------------------------------------------------
PROB_IMPULSE: int = 16        # 1/16 chance of thrust per tick
PROB_PHOTON: int = 8          # 1/8 chance of firing per tick (Klingon)
PROB_HYPER: int = 1024        # 1/1024 chance of hyperspace per tick

# ---------------------------------------------------------------------------
# Object table indices                 (GENERAL.EQU word offsets ÷ 2)
# ---------------------------------------------------------------------------
ENT_OBJ: int = 0              # Enterprise ship
KLN_OBJ: int = 8              # Klingon ship
ENT_TORP_START: int = 1       # First Enterprise torpedo slot
ENT_TORP_END: int = 8         # One past last (slots 1-7)
KLN_TORP_START: int = 9       # First Klingon torpedo slot
KLN_TORP_END: int = 16        # One past last (slots 9-15)
NUM_OBJECTS: int = 16         # Total slots in object table

# EFLG values
EFLG_INACTIVE: int = 0
EFLG_ACTIVE: int = 1
EFLG_EXPLODING: int = -1

# UFLG bits
REDRAW_BIT: int = 0x01

# FLAGS bits
THRUST_BIT: int = 0x01
CLOAK_BIT: int = 0x02

# FIRE bits
TORP_FIRE_BIT: int = 0x01
HYPER_FIRE_BIT: int = 0x02

# PLANET_ENABLE bits
PLANET_BIT: int = 0x01        # BIT0 — planet visible + collision active
GRAVITY_BIT: int = 0x02       # BIT1 — gravity active

# AUTO_FLAG bits
AUTO_ENT_BIT: int = 0x01      # BIT0 — Enterprise robot active
AUTO_KLN_BIT: int = 0x02      # BIT1 — Klingon robot active

# ---------------------------------------------------------------------------
# Game modes
# ---------------------------------------------------------------------------
MODE_ATTRACT: int = 0
MODE_PLAY: int = 1

# ---------------------------------------------------------------------------
# Hyperspace animation
# ---------------------------------------------------------------------------
HYPER_DURATION: int = 64      # Ticks for hyperspace animation (split 50/50 expand/contract)
HYPER_PHASE: int = 32         # Ticks per expand/contract phase (HYPER_DURATION // 2)
HYPER_PARTICLES: int = 32     # Particles per ship
EXPLOSION_FRAMES: int = 8     # Number of explosion animation frames
SHIP_EXPLOSION_TICKS: int = 40  # exps value set on ship death (≈0.55 s at 73 fps)

# ---------------------------------------------------------------------------
# Attract mode
# ---------------------------------------------------------------------------
ATTRACT_SCREENS: int = 4      # Number of attract screen pages
ATTRACT_CYCLE_TIME: int = 500 # Ticks per attract screen
