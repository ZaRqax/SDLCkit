#!/usr/bin/env bash
# setup.sh — bootstrap the Open-Model SDLC Kit. Idempotent; safe to re-run.
#   ./setup.sh [pi|qwen|crush|opencode|claude]   (omit to be prompted)
#   ./setup.sh --plugin-mirror                   (mirror .claude/* to plugin-root layout)
#   ./setup.sh --check                           (just run the verifier)
set -euo pipefail
KIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$KIT_DIR"

bold() { printf '\033[1m%s\033[0m\n' "$1"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$1"; }
info() { printf '  • %s\n' "$1"; }
have() { command -v "$1" >/dev/null 2>&1; }

# --- subcommands ---------------------------------------------------------------
case "${1:-}" in
  --check) exec bash "$KIT_DIR/scripts/check-kit.sh" ;;
  --plugin-mirror)
    bold "Mirroring .claude/{agents,commands,skills} → plugin-root layout"
    for d in agents commands skills; do
      [ -d ".claude/$d" ] && { rm -rf "./$d"; cp -r ".claude/$d" "./$d"; ok "$d/"; }
    done
    mkdir -p hooks; cp .claude/hooks/* hooks/ 2>/dev/null || true
    cat > hooks/hooks.json <<'JSON'
{ "hooks": {
  "PreToolUse": [
    { "matcher": "Edit|Write|MultiEdit", "hooks": [{ "type": "command", "command": "bash ${CLAUDE_PLUGIN_ROOT}/hooks/format-and-guard.sh pre-edit", "timeout": 10 }] },
    { "matcher": "Bash", "hooks": [{ "type": "command", "command": "bash ${CLAUDE_PLUGIN_ROOT}/hooks/format-and-guard.sh pre-bash", "timeout": 10 }] }
  ],
  "PostToolUse": [
    { "matcher": "Edit|Write|MultiEdit", "hooks": [{ "type": "command", "command": "bash ${CLAUDE_PLUGIN_ROOT}/hooks/format-and-guard.sh post-edit", "timeout": 30 }] }
  ]
} }
JSON
    ok "hooks/hooks.json"
    info "Now installable as a plugin: /plugin marketplace add $KIT_DIR  then  /plugin install open-model-sdlc-kit"
    exit 0 ;;
esac

# --- 1. prerequisites ----------------------------------------------------------
bold "1. Checking prerequisites"
for c in uv uvx; do have "$c" && ok "$c" || warn "$c missing — needed for Serena, git & fetch MCP (https://docs.astral.sh/uv/)"; done
have node && ok "node $(node -v)" || warn "node missing — needed for npx MCP servers, pi, Qwen Code (Node 18+)"
have docker && ok "docker" || warn "docker missing — needed for the Atlassian MCP server"
have task && ok "go-task" || warn "go-task missing — the workspace build runner (https://taskfile.dev)"
have gofumpt || warn "gofumpt missing — the format hook will fall back to gofmt (go install mvdan.cc/gofumpt@latest)"

# --- 2. env --------------------------------------------------------------------
bold "2. Environment"
if [ ! -f .env ]; then cp .env.example .env; ok "created .env from .env.example — EDIT IT (GITHUB_PAT, JIRA_*, OPENAI_*)"; else ok ".env exists"; fi
# shellcheck disable=SC1091
set -a; [ -f .env ] && . ./.env; set +a
[ -n "${GITHUB_PAT:-}" ] && ok "GITHUB_PAT set (Serena can index private modules)" || warn "GITHUB_PAT empty — Serena find_symbol will be empty on github.com/acme modules"
[ -n "${OPENAI_BASE_URL:-}" ] && ok "OPENAI_BASE_URL=$OPENAI_BASE_URL" || warn "OPENAI_BASE_URL empty — set your open-model /v1 endpoint"

# --- 3. CLAUDE.md ↔ AGENTS.md bridge ------------------------------------------
bold "3. Instruction bridge"
if head -1 CLAUDE.md | grep -q '@AGENTS.md'; then ok "CLAUDE.md imports AGENTS.md"; else warn "CLAUDE.md does not start with @AGENTS.md — check it"; fi

# --- 4. git hooks (open-agent guardrail fallback) ------------------------------
bold "4. Git hooks"
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  chmod +x .githooks/pre-commit
  git config core.hooksPath .githooks && ok "core.hooksPath → .githooks (guardrails enforced on commit)"
else
  warn "not a git repo — run 'git init && git config core.hooksPath .githooks' after adopting the kit"
fi
chmod +x .claude/hooks/*.sh scripts/*.sh 2>/dev/null || true

# --- 5. agent selection --------------------------------------------------------
bold "5. Agent setup"
AGENT="${1:-}"
if [ -z "$AGENT" ]; then
  echo "  Which agent? [pi] qwen crush opencode claude"
  read -r -p "  > " AGENT || true; AGENT="${AGENT:-pi}"
fi
PI_DIR="${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}"
case "$AGENT" in
  pi)
    PI_BIN="${PI_BIN:-pi}"
    mkdir -p "$PI_DIR/extensions/mcp-bridge" "$PI_DIR/extensions/subagent" "$PI_DIR/agents"
    # core config
    cp agents-config/pi/models.json          "$PI_DIR/models.json"
    cp agents-config/pi/mcp.json             "$PI_DIR/mcp.json"
    cp agents-config/pi/SYSTEM.md            "$PI_DIR/APPEND_SYSTEM.md"
    cp agents-config/pi/settings.json        "$PI_DIR/settings.json"
    cp agents-config/pi/subagent-config.json "$PI_DIR/extensions/subagent/config.json"
    ok "pi core config → $PI_DIR (models, mcp, settings, APPEND_SYSTEM, subagent config)"
    # specialist subagents — generated from the canonical .claude/agents (pi-subagents format)
    if have python3; then
      python3 agents-config/pi/port-agents.py "$PI_DIR/agents" >/dev/null 2>&1 \
        && ok "6 subagents → $PI_DIR/agents/ (generated from .claude/agents)" \
        || warn "port-agents.py failed — run: python3 agents-config/pi/port-agents.py $PI_DIR/agents"
    else warn "python3 missing — can't generate pi subagents; run port-agents.py manually"; fi
    # custom MCP bridge — staged as a DISABLED fallback (not in settings.json packages[])
    cp agents-config/pi/mcp-extension/src/index.ts "$PI_DIR/extensions/mcp-bridge/index.ts"
    cp agents-config/pi/mcp-extension/package.json "$PI_DIR/extensions/mcp-bridge/package.json"
    ( cd "$PI_DIR/extensions/mcp-bridge" && have npm && npm install >/dev/null 2>&1 ) \
      && info "fallback MCP bridge staged (disabled) in $PI_DIR/extensions/mcp-bridge" \
      || warn "fallback bridge: run 'npm install' in $PI_DIR/extensions/mcp-bridge if you ever enable it"
    # ecosystem packages (auto-register into settings.json on install)
    if have "$PI_BIN"; then
      for p in npm:pi-mcp-adapter@2.10.0 npm:pi-subagents@0.31.0 npm:@pi-vault/pi-plan@0.1.0 npm:pi-patty-bg-tasks@0.2.0; do
        "$PI_BIN" install "$p" >/dev/null 2>&1 && ok "installed $p" || warn "pi install $p failed — run it manually"
      done
      info "pi-mcp-adapter reads $PI_DIR/mcp.json automatically (no /mcp setup needed)"
      info "note: @pi-vault/pi-plan requires Node >=24.15.0 — upgrade Node if /plan errors"
    else
      warn "pi CLI not found — install '@earendil-works/pi-coding-agent', then:"
      info "  pi install npm:pi-mcp-adapter@2.10.0 npm:pi-subagents@0.31.0 npm:@pi-vault/pi-plan@0.1.0 npm:pi-patty-bg-tasks@0.2.0"
    fi
    info "Start:  set -a; source $KIT_DIR/.env; set +a;  pi --model selfhosted/Qwen3-Coder-Next"
    info "Verify: /mcp · /mcp tools · /run planner \"spec PROJ-1234\" · /plan · /bg-list"
    info "Optional: pi install npm:@geminixiang/pi-diff  (then /diff) — see agents-config/pi/README.md" ;;
  qwen)
    mkdir -p .qwen; cp agents-config/qwen/.qwen/settings.json .qwen/settings.json
    [ -f .qwen/.env ] || cp agents-config/qwen/.qwen/.env.example .qwen/.env
    ok "Qwen Code config → ./.qwen (settings.json + .env) — edit .qwen/.env for your endpoint"
    info "Start:  qwen   (reads AGENTS.md + .qwen/settings.json)" ;;
  crush)
    cp agents-config/crush/crush.json ./crush.json
    ok "Crush config → ./crush.json (reads AGENTS.md automatically)"
    info "Start:  set -a; source .env; set +a;  crush" ;;
  opencode)
    cp agents-config/opencode/opencode.json ./opencode.json
    ok "opencode config → ./opencode.json"
    info "Start:  set -a; source .env; set +a;  opencode" ;;
  claude)
    ok "Claude Code uses .mcp.json + .claude/ directly — nothing to copy"
    info "Start: run 'claude' here; approve the project MCP servers when prompted (/mcp)." ;;
  *) warn "unknown agent '$AGENT' — choose pi|qwen|crush|opencode|claude"; exit 1 ;;
esac

# --- 6. verify -----------------------------------------------------------------
bold "6. Verifying"
bash "$KIT_DIR/scripts/check-kit.sh" || true
echo
bold "Done. Next: fill .env, then drive a ticket through the pipeline (see FLOW.md)."
