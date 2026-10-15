#!/usr/bin/env bash
# Retained legacy entrypoint. Source roles are immutable under enablement changes.
set -euo pipefail
KIT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$KIT_ROOT"
python3 scripts/pipeline_config.py check
python3 scripts/render-role-bridges.py --check
if [ "${1:-}" = "--reconcile-only" ]; then
  echo "role selection validated; canonical sources preserved"
  exit 0
fi
python3 agents-config/pi/port-agents.py
if [ -d .opencode ]; then
  python3 agents-config/opencode/port-to-opencode.py .opencode
fi
if [ -d .qwen/agents ]; then
  python3 agents-config/qwen/port-to-qwen.py .qwen
fi
# Target adapters are reconciled by setup.sh --target … using the ownership manifest.
echo "legacy adapters regenerated; use setup.sh --target PATH for selected native harnesses"
