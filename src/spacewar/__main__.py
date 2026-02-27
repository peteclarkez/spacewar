"""
Entry point — parses CLI arguments and launches the game.

Usage:
    python -m spacewar
    spacewar --scale 2
    spacewar --2x
    spacewar --scale 3        # 3× window + neon mode easter egg
    spacewar --neon
    spacewar --altkeys
"""

from __future__ import annotations
import argparse
import sys


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="spacewar",
        description="SpaceWar 1985 — faithful Python/Pygame recreation",
    )
    p.add_argument(
        "--scale", type=int, default=1, metavar="N",
        help="Scale the window by N (default 1 = 640×480)",
    )
    p.add_argument(
        "--2x", dest="two_x", action="store_true",
        help="Alias for --scale 2 (1280×960)",
    )
    p.add_argument(
        "--neon", action="store_true",
        help="Neon colour mode — coloured glow halos on all sprites",
    )
    p.add_argument(
        "--altkeys", action="store_true",
        help="Replace Klingon numpad layout with UIO / JKL / M,. keys",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    scale = args.scale
    neon  = args.neon

    if args.two_x:
        scale = 2
    if scale == 3:          # Easter egg: 3× always enables neon
        neon = True

    scale = max(1, scale)   # Guard against silly values

    from spacewar.game import Game
    game = Game(scale=scale, neon=neon, altkeys=args.altkeys)
    game.run()


if __name__ == "__main__":
    main()
