#!/usr/bin/env python3
"""SDLCkit unified entry point."""
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sdlc.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
