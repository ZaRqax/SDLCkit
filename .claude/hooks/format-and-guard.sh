#!/usr/bin/env bash
# Shared Claude/Qwen guard. The Python effect policy is also used by the CLI.
set -euo pipefail
KIT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export PYTHONPATH="$KIT_ROOT${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m sdlc.policy "${1:-}"
