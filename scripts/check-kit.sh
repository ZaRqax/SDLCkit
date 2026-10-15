#!/usr/bin/env bash
# Structural/schema checks; --test adds deterministic offline regression/integration tests.
set -euo pipefail
KIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$KIT_DIR"
export PYTHONDONTWRITEBYTECODE=1
python3 scripts/check_kit.py
case "${1:-}" in
  --test) python3 -m unittest discover -s tests -v ;;
  --mcp) python3 scripts/sdlc.py doctor --target "$KIT_DIR" ;;
  ''|--structural) ;;
  *) printf 'usage: %s [--test|--mcp|--structural]\n' "$0" >&2; exit 2 ;;
esac
