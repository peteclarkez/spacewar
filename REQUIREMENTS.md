
# Requirements: SpaceWar 1985 (v1.72) Faithful Recreation
> Derived from: the original game manual (`spacewar.doc.txt`), Bill Seiler's v1.50 Assembly source code (1985), and reference screenshots.

---

## 1. Visual Aesthetic & Display

*   **Style:** Monochrome (Black & White) high-contrast vector style.
*   **Native Resolution:** 640×200 (CGA Color Card original). Recreate at **640×480** to approximate the original CGA aspect ratio by doubling the Y-axis.
*   **Coordinate System:** All game logic should operate in a virtual 640×200 space; rendering scales to 640×480.
*   **Ship Design:** Open-crescent "C" shape with a center pixel dot. Enterprise and Klingon ships are mirror images of each other (Klingon faces left at start, Enterprise faces right).
*   **Background:** **512 static, single-pixel white dots** (Starfield), placed randomly within the active screen area (excluding the 8-pixel wrap border).
*   **Planet:** A central animated circle containing horizontal scanlines. The planet sprite cycles through **16 animation states**, advancing one state every **16 game ticks** (visible only when the Planet toggle is ON).
*   **Energy Bars:** Two sets of energy bars drawn at the bottom of the screen. Each set shows an 'S' (Shield) bar and an 'E' (Energy/Dilithium) bar. The 'S' label blinks off when shields are critically low.
*   **Explosions (Torpedoes):** Small expanding sprite animation. Object flag cycles through states (incremented by 2 per tick), drawing a new explosion graphic every 8 states, until overflow.
*   **Explosions (Ship/Hyperspace):** The ship's hull disintegrates into **32 individual pixel particles** that scatter outward with random velocities.

---

## 2. Angle & Rotation System

*   **Angle Unit:** A full circle is **256 units** (not 360 degrees). All angles, trig lookups, and rotations use this system.
*   **Trig Lookup:** Sine and Cosine are retrieved from a pre-computed 256-entry lookup table. Values range from **-32767 to +32767** (fixed-point, where 32767 ≈ 1.0).
*   **Starting Angles:**
    *   Enterprise (P1 / Left): Angle **0** (facing right / East).
    *   Klingon (P2 / Right): Angle **128** (facing left / West).
*   **Rotation Rate:** Each held rotation key changes the ship's angle by **±2 units per game tick** (out of 256).

---

## 3. Physics & Celestial Mechanics

### 3.1 Starting Positions
*   **Enterprise (P1):** Spawns at 1/4 of the screen width, 1/4 of the playfield height. In 640×200 coords: approximately **(160, 46)**.
*   **Klingon (P2):** Spawns at 3/4 of screen width, 3/4 of playfield height. In 640×200 coords: approximately **(480, 138)**.
*   All ships spawn with **zero velocity**.

### 3.2 Zero-Friction Inertia
Newton's First Law applies. Ships maintain velocity unless thrust is applied in the opposite direction.

### 3.3 Screen Wrapping
*   All game objects (ships, torpedoes, phaser rays, hyperspace particles) wrap at screen edges.
*   **Wrap Factor:** A **WRAP_FACTOR of 8 pixels** creates a small overlap zone — objects re-appear 8 pixels in from the opposite edge when they exit.
*   Formula: if `x < WRAP_FACTOR` → `x += MAX_X - (2 * WRAP_FACTOR)` (and symmetrically for overflow).

### 3.4 Velocity Cap
*   Maximum velocity in each axis: **±8 units** (integer high-word of the velocity dword).
*   If thrust would exceed the cap, the thrust acceleration for that axis is discarded.

### 3.5 Gravity — "Bowl Gravity" (Linear, NOT Inverse-Square)
> **Critical:** The original source uses linear "bowl" gravity, **not** an inverse-square law. The ASM comment explicitly calls it "bowl gravity."

*   **Toggle:** Gravity is independently toggled by **F6** (separate from the planet's visibility).
*   **Formula:** Gravity acceleration applied each tick is proportional to displacement from centre, multiplied by 8.
    *   `accel_x = -(obj_x - PLANET_X) * 8`
    *   `accel_y = -(obj_y - PLANET_Y) * 8`
    *   Implemented by left-shifting the distance value by 3 (`shl bx,1; shl bx,1; shl bx,1`).
*   Gravity affects **all active objects**: both ships and all torpedoes in flight.
*   Planet is at screen centre: **(319, 99)** in 640×200 coordinates.
*   **Planet Range (Collision Radius):** 16 pixels.

### 3.6 Thrust Acceleration
*   Thrust force per tick is the ship's facing vector (from trig table), **right-shifted 3 times** (divided by 8). This is `ACCEL_SCALE = 3`.

---

## 4. Energy & Shield Management (The Balance System)

### 4.1 Starting Values
*   **Shield Energy (S):** Starts at **31 units** per ship.
*   **General Energy (E):** Starts at **127 units** per ship.

### 4.2 'E' Bar (General / Dilithium Energy)
*   Used for: Thrusting, Cloaking, Firing Phasers, Firing Torpedoes, and Hyperspace.
*   **Recharge:** +1 unit every **256 game ticks** (~3.5 seconds at 72.8 Hz). No recharge if energy is at zero.
*   Energy is stored as a signed byte. If it reaches 127 (MSB set = negative in signed), recharge stops.

### 4.3 'S' Bar (Shield Energy)
*   **Does NOT recharge automatically.**
*   Protects the ship from destruction.
*   **Death Condition:** A ship is destroyed when its Shield value goes **negative** (bit 7 set, i.e., has wrapped below 0 via damage). A ship at exactly 0 is alive but will die on the next hit.

### 4.4 Energy Transfer (Balance Keys)
*   Players manually transfer 1 unit at a time between S and E.
*   **Rate:** One unit transfers every **4 game ticks** while the key is held (`SWAP_TIME = 4`).
*   Transfer is blocked if the source bar is at 0 (cannot go negative).
*   Key held down = continuous transfer at the above rate.

### 4.5 Energy Costs (Timing Reference)
The game timer runs at approximately **72.8 interrupts/second** (system clock / 16390).

| Action | Cost | Period |
|---|---|---|
| Thrust (Impulse) | 1 unit | Every 32 ticks (~0.44 s) |
| Cloak | 1 unit | Every 32 ticks (~0.44 s) |
| Phaser Fire | 1 unit | On keypress |
| Photon Torpedo Launch | 1 unit | On keypress |
| Hyperspace | 8 units | On keypress |
| Energy Recharge | +1 unit | Every 256 ticks (~3.5 s) |

---

## 5. Combat & Weapons

### 5.1 Photon Torpedoes
*   **Cost:** 1 unit of E-Energy per torpedo fired.
*   **Simultaneous Limit:** Each ship may have up to **7 torpedoes** in flight at once (ENTTORP0–ENTTORP6 / KLNTORP0–KLNTORP6). Firing is blocked if all 7 slots are active.
*   **Torpedo Key:** Debounced — the key must be released and re-pressed to fire another torpedo.
*   **Initial Velocity:** Torpedo velocity = ship's current velocity + firing direction vector scaled by **4x** (`FIRE_SCALE = 2`, left-shifted twice). Torpedo spawns offset from ship centre along the firing axis.
*   **Lifespan/Energy:** Each torpedo has **40 energy units**. It loses 1 unit every **16 ticks** (~0.22 s). After ~8.8 seconds (640 ticks), the torpedo expires and begins its explosion animation.
*   **Torpedo Gravity:** Affected by gravity when gravity is ON.
*   **Damage:** **4 units** of Shield Energy on a hit (`PHOTON_DAMAGE = 4`).
*   **Self-Hit:** Both players' own torpedoes can hit their own ship. All combinations are checked: ent-vs-kln torps, ent-vs-ent torps, kln-vs-ent torps, kln-vs-kln torps.
*   **Torpedo-vs-Torpedo:** Torpedoes from opposing ships can collide and annihilate each other (`TORP_TO_TORP_RANGE = 6` pixels).

### 5.2 Phasers
*   **Cost:** 1 unit of E-Energy per shot.
*   **Cooldown:** After firing, a **24-tick cooldown** (`PHASER_DELAY = 24`) before firing again. The phaser ray is erased at the **20-tick** mark (`PHASER_ERASE = 20`).
*   **Appearance:** A line segment traced pixel by pixel from the ship outward. The first **9 pixels** are skipped (dead zone around the ship to prevent self-hits).
*   **Maximum Range:** **96 pixels** in virtual 640×200 coordinates (`PHASER_RANGE = 96`).
*   **Hit Detection:** A hit is checked every **8 pixels** along the ray (`PHASER_TO_OBJ_RANGE = 8`, must be a power of 2). Hit box radius is 8 pixels.
*   **Damage to Ships:** **2 units** of Shield Energy (`PHASER_DAMAGE = 2`).
*   **Shooting Down Torpedoes:** A phaser ray that passes within 8 pixels of an active torpedo destroys it (triggers its explosion animation). This stops the phaser ray.
*   **Planet Interaction:** The phaser ray also terminates if it hits the Planet (when planet is active).
*   **Sound:** Triggers a ramping pitch "phaser" tone that rises then cuts off.

### 5.3 Cloak
*   **Cost:** 1 unit of E-Energy every **32 ticks** (~0.44 s) while active.
*   **Effect:** Ship becomes **invisible to both players**. The ship's position, velocity, and collision detection remain fully active while cloaked.
*   **Activation:** Active while key is held, deactivates on release.

### 5.4 Hyperspace
*   **Cost:** 8 units of E-Energy (deducted immediately on keypress).
*   **Debounced:** Key must be released and re-pressed to activate again.
*   **Animation (64 ticks total):**
    1.  Ship disappears. 32 particles scatter from the ship's position with random velocities (influenced by the ship's current momentum).
    2.  At tick 32: particles' velocities are negated — they begin converging toward a new random destination.
    3.  At tick 64: particles disappear, ship reappears at the new destination.
*   **On Arrival:** Ship spawns at a random position. **All velocity is zeroed** (ship arrives stationary).
*   **Sound:** Triggers hyperspace sound (pitch based on animation progress).

### 5.5 Ship-to-Ship Collision
*   **Detection Range:** 16 pixels (`SHIP_TO_SHIP_RANGE = 16`).
*   **Effect:** An **inelastic velocity swap** — each ship takes on half of the other's velocity. Ships are pushed apart by **2 pixels** (`BOUNCE_FACTOR = 2`).
*   **No Shield Damage** is applied for a ship-to-ship collision.

### 5.6 Destruction Logic
A ship is destroyed when its Shield value underflows below zero (damage pushes it negative). At that moment:
1.  The ship is erased from the screen.
2.  Ship decomposes into 32 pixel particles with random velocities (explosion animation, ~128–256 animation steps).
3.  Opponent's score increments by 1.
4.  Game transitions to **Attract Mode** (scores are preserved).

---

## 6. Game Modes & AI (Robots)

### 6.1 Attract Mode
*   The default non-playable state when no game is running.
*   Displays the **"SPACEWAR" title** as individual letter blocks, which **explode apart and reform** in a looping animation.
*   Cycles through the following screens in a loop:
    1.  Copyright info (`COPYRIGHT © 1985 B SEILER`) and current scores.
    2.  Game Instructions (text: object, weapons, defense, energy rules).
    3.  Key Instructions (graphical keyboard layout boxes).
    4.  User-Supported Software message.
*   The **Planet** is displayed at the **top-right of the screen** in attract mode (not the center).
*   Function keys remain active during attract mode.

### 6.2 Scoring
*   Scores (Enterprise wins, Klingon wins) are **persistent across games** within a session.
*   Displayed in attract mode next to small ship icons.

### 6.3 Left Robot (F3) — Enterprise Auto / "Defensive"
Activated by F3 (`RANDOM_ROBOT_KEY`). Controls the **Enterprise (P1)**.

*   **Energy Balance:** Continuously balances S and E bars towards equality (transfers 1 unit per swap period).
*   **If out of energy:** Disables impulse and phasers.
*   **Targeting:** Scans all active Klingon objects. If any active object is within **PHASER_RANGE (96 pixels)** in both X and Y, calculates the exact bearing angle using an arctangent lookup table.
*   **Firing:** Fires **phasers only** when an object is in range. Does **not** fire photon torpedoes.
*   **Movement:** Random impulse thrust. Probability per tick: **1/16** (`PROB_IMPULSE = 16`).
*   **Hyperspace:** Random hyperspace. Probability per tick: **1/1024** (`PROB_HYPER = 1024`, very rare).

### 6.4 Right Robot (F4) — Klingon Auto / "Offensive"
Activated by F4 (`SMART_ROBOT_KEY`). Controls the **Klingon (P2)**.

*   **Aim:** Always rotates to face the Enterprise directly. Calculates exact bearing using atan lookup.
*   **Energy Balance:** Same as Left Robot — continuously balances S and E.
*   **If out of energy:** Disables impulse and photon fire.
*   **Firing:** Random chance to fire each tick (probability **1/8**, `PROB_PHOTON = 8`). When it fires:
    *   If Enterprise is within **PHASER_RANGE in both axes**: fires **phasers**.
    *   Otherwise: fires **photon torpedoes**.
*   **Movement:** Random impulse, probability **1/16**.
*   **Hyperspace:** Random hyperspace, probability **1/1024**.

---

## 7. Key Bindings & UI

### 7.1 Function Keys (Global — Active in Attract & Play Modes)

| Key | Function | Notes |
|:---|:---|:---|
| **F1** | Exit to Attract Mode / DOS | |
| **F2** | Start Game | |
| **F3** | Toggle Left Robot (Enterprise Auto) | Highlighted when active |
| **F4** | Toggle Right Robot (Klingon Auto) | Highlighted when active |
| **F5** | Toggle Planet | Toggles planet visibility AND collision hazard |
| **F6** | Toggle Gravity | Independent of planet visibility |
| **F7** | Pause | Halts all game logic |
| **F8** | Toggle Sound | |

> **Note:** F5 = Planet, F6 = Gravity. These are **separate, independent toggles**. Gravity can be on without the planet being visible and vice versa.

### 7.2 Player Controls

| Action | Left Player (P1) | Right Player (P2 — Numpad) |
| :--- | :--- | :--- |
| **Fire Phasers** | Q | 7 |
| **Cloak Ship** | W | 8 |
| **Fire Photon Torpedo** | E | 9 |
| **Rotate CCW** | A | 4 |
| **Impulse (Thrust)** | S | 5 |
| **Rotate CW** | D | 6 |
| **Shields → Energy** | Z | 1 |
| **Hyperspace** | X | 2 |
| **Energy → Shields** | C | 3 |

### 7.3 Function Key Footer
*   A row of labeled function key boxes is displayed at the **bottom of the screen** at all times.
*   Active toggles (Robot, Planet, Gravity, Pause) are shown **inverted/highlighted**.

---

## 8. Audio & Alerts

*   **Sound System:** Driven by a priority flag byte (`SOUND_FLAG`). Only one sound plays at a time. Priority (highest first):
    1.  **Hyperspace Sound** — pitch varies based on animation progress.
    2.  **Phaser Sound** — a rising pitch ramp (`PHASER_SOUND_RAMP = 8` per tick), cuts to silence when ramp overflows.
    3.  **Photon Fire Sound** — a brief high-pitched bleep, lasting **2 ticks** only.
    4.  **Warning Sound** — alternates between a high pitch and a low pitch, toggling every **32 ticks** (`WARNING_TIME`).
    5.  **Explosion Sound** — random noise burst while an explosion is playing.
*   **Warning Trigger:** Activates when a ship's Shield bar falls below **16 units** (`LOW_SHIELD_LIMIT`). The 'S' label also blinks on the energy bar.
*   **Sound Toggle:** F8 turns all sound on or off.

---

## 9. State Logic & Edge Cases

### 9.1 Planet Hazard
*   When the Planet is **active (F5 ON)**: any object entering within **16 pixels** of the planet centre takes damage.
    *   Ships: lose **2 Shield units** per collision check (`PLANET_DAMAGE = 2`).
    *   Torpedoes: are immediately destroyed (begin explosion animation).

### 9.2 Game Reset
*   On ship destruction: transition to **Attract Mode**. Scores are preserved.
*   Starting a new game (F2) resets all ship positions, velocities, and energy bars to starting values. Scores are NOT reset by starting a game.

### 9.3 Object Table
The game tracks **16 objects** total in a unified table (indexed by word offset):

| Index | Object |
|---|---|
| 0 | Enterprise (P1 Ship) |
| 1–7 | Enterprise Torpedoes 0–6 |
| 8 | Klingon (P2 Ship) |
| 9–15 | Klingon Torpedoes 0–6 |

---

## 10. Precise Numeric Constants (Source-Verified)

Exact values extracted from the v1.50 Assembly source for reference when tuning the recreation.

| Constant | Value | Source | Description |
|:---|:---|:---|:---|
| `MAX_X_AXIS` | 640 | GENERAL.EQU | Screen width (CGA) |
| `MAX_Y_AXIS` | 200 | GENERAL.EQU | Screen height (CGA) |
| `WRAP_FACTOR` | 8 | GENERAL.EQU | Screen-edge wrap overlap |
| `MAX_X_VELOCITY` | 8 | GENERAL.EQU | Max velocity per axis |
| `MAX_Y_VELOCITY` | 8 | GENERAL.EQU | Max velocity per axis |
| `STAR_COUNT` | 512 | STARS.ASM | Stars on CGA display |
| `PLANET_X` | 319 | PLANET.EQU | Planet centre X (640/2 - 1) |
| `PLANET_Y` | 99 | PLANET.EQU | Planet centre Y (200/2 - 1) |
| `PLANET_RANGE` | 16 | PLANET.EQU | Planet collision radius (pixels) |
| `PLANET_TIME` | 16 | PLANET.EQU | Planet animation speed (ticks/frame) |
| `ROTATE_RATE` | 2 | MAIN.ASM | Rotation speed (units/tick, 256/circle) |
| `ACCEL_SCALE` | 3 | PLAYINT.ASM | Thrust accel right-shift (÷8) |
| `FIRE_SCALE` | 2 | TORP.ASM | Torpedo velocity left-shift (×4) |
| `HYPERSPACE_ENERGY` | 8 | MAIN.ASM | Hyperspace E-energy cost |
| `PHOTON_LAUNCH_ENERGY` | 1 | TORP.ASM | Torpedo launch E-energy cost |
| `PHOTON_ENERGY` | 40 | TORP.ASM | Torpedo starting energy (lifespan) |
| `PHOTON_DAMAGE` | 4 | CMPS.ASM | Torpedo shield damage |
| `PHASER_FIRE_ENERGY` | 1 | PHASER.EQU | Phaser E-energy cost |
| `PHASER_RANGE` | 96 | PHASER.EQU | Phaser max length (pixels) |
| `PHASER_ERASE` | 20 | PHASER.EQU | Phaser ray erase tick |
| `PHASER_DELAY` | 24 | PHASER.EQU | Phaser cooldown (ticks) |
| `PHASER_TO_OBJ_RANGE` | 8 | PHASER.EQU | Phaser hit-check radius (px, PoT) |
| `PHASER_DAMAGE` | 2 | PHASER.EQU | Phaser shield damage |
| `SHIP_TO_SHIP_RANGE` | 16 | CMPS.ASM | Ship collision range (pixels) |
| `SHIP_TO_TORP_RANGE` | 8 | CMPS.ASM | Ship-torpedo hit range (pixels) |
| `TORP_TO_TORP_RANGE` | 6 | CMPS.ASM | Torp-torp collision range (pixels) |
| `BOUNCE_FACTOR` | 2 | CMPS.ASM | Ship-ship bounce separation (pixels) |
| `PLANET_DAMAGE` | 2 | CMPS.ASM | Planet shield drain per check |
| `LOW_SHIELD_LIMIT` | 16 | PLAYINT.ASM | Warning sound/blink threshold |
| `SWAP_TIME` | 4 | MAIN.ASM | Energy transfer rate (ticks/unit) |
| `IMPULSE_TIME` | 32 | PLAYINT.EQU | Thrust energy cost period (ticks) |
| `CLOAK_TIME` | 32 | PLAYINT.EQU | Cloak energy cost period (ticks) |
| `DILITHIUM_TIME` | 256 | PLAYINT.EQU | E-energy recharge period (ticks) |
| `PHOTON_TIME` | 16 | PLAYINT.EQU | Torpedo energy drain period (ticks) |
| `WARNING_TIME` | 32 | PLAYINT.EQU | Warning sound alternation (ticks) |
| `PROB_IMPULSE` | 16 | MAIN.ASM | Robot thrust probability (1/N per tick) |
| `PROB_PHOTON` | 8 | MAIN.ASM | Robot photon probability (1/N per tick) |
| `PROB_HYPER` | 1024 | MAIN.ASM | Robot hyperspace probability (1/N per tick) |
| `STARTING_SHIELDS` | 31 | INIT.ASM | Initial shield energy per ship |
| `STARTING_ENERGY` | 127 | INIT.ASM | Initial E-energy per ship |
| `GAME_TIMER_HZ` | ~72.8 | MAIN.ASM | Interrupt rate (1,193,180 / 16390) |
