"""PyInstaller entry point for SpaceWar."""
import sys
import os

# Ensure the src directory is on the path when running as a frozen executable
if getattr(sys, 'frozen', False):
    sys.path.insert(0, os.path.join(sys._MEIPASS, 'src'))

from spacewar.main import main

if __name__ == '__main__':
    main()
