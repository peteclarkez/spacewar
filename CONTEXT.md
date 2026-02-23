
# Context Overview: SpaceWar 1985 (v1.72) Recreation Project

> This overview is designed to be pasted into a new conversation with any AI coding assistant to provide immediate context on the project's history, technical requirements, and current status.

### 1. Project Goal
The objective is a faithful 1:1 recreation of **SpaceWar v1.72 (1985/86)** originally developed by **Bill Seiler** for DOS. The recreation is being built in **Python** using the **Pygame** library, focusing on replicating the exact physics, monochrome vector aesthetic, and unique "Energy Balance" mechanics of the original.

### 2. Reference Materials Retained
*   **Requirements Document:** A detailed Markdown file (`spacewar_requirements.md`) based on the original game manual (`spacewar.doc`).
*   **Original Source Code:** The assembly source code for **version 1.50** has been located for reference on logic, gravity mathematics, and torpedo physics.
*   **Current Python Build:** A functional Pygame script that implements ship movement, dual energy meters (S and E), gravity, a central planet with moons, and vertex-based explosion debris.

### 3. Core Mechanics Architecture
The project must adhere to these specific (often overlooked) mechanics from the 1985 version:
*   **Dual-Meter System:** Ships have **Weapon/General Energy (E)** and **Shield Energy (S)**. 
*   **Energy Balance:** Energy does not auto-transfer. Players must use keys to manually move units from `S to E` or `E to S`.
*   **Damage Model:** A ship is only destroyed if hit when its `S` bar is at zero. Otherwise, hits simply deplete shield units.
*   **Phasers vs. Torpedoes:** Phasers are not just weapons; they are defensive tools used to shoot down incoming photon torpedoes.
*   **Gravity & Orbits:** Torpedoes must be influenced by the central gravity well, allowing for "slingshot" shots.
*   **Cloaking:** The ship becomes invisible to **both** the opponent and the player controlling it.

### 4. Technical Progress to Date
*   **Visuals:** Completed the monochrome crescent ship design and the animated planet with horizontal scanlines and orbiting moons.
*   **Physics:** Implemented zero-friction inertia, screen wrapping, and inverse-square gravity.
*   **Explosions:** Implemented a system where the ship's hull vertices shatter into individual points that expand based on the ship's final velocity.
*   **UI:** Implemented a function-key footer (F1–F8) to toggle game features (Gravity, Planet, Robots) and handle resets.

### 5. Current Development State
The current Python code is stable for 2-player combat. The next phases of development involve:
1.  **Robot AI:** Implementing the "Left" (Defensive) and "Right" (Offensive) Auto-Robot players.
2.  **Sound System:** Adding the 8-bit warning tones for low shields and white-noise bursts for engines/torpedoes.
3.  **Refinement:** Fine-tuning the gravity constant and energy recharge rates to match the "feel" of the 1985 original.

### 6. Suggested Prompt to Resume
*"I am working on a recreation of SpaceWar 1985. I have the requirements document and the original v1.50 assembly source for reference. We have a working Pygame base with gravity and energy balance. I would like to move on to [insert next step, e.g., 'implementing the AI Robot players' or 'refining the torpedo gravity physics']."*