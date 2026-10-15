"""Run the same local CLI as scripts/sdlc.py."""
import sys

sys.dont_write_bytecode = True
from .cli import main

raise SystemExit(main())
