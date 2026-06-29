#!/usr/bin/env bash
# setup.sh — bootstrap the Open-Model SDLC Kit. Idempotent; safe to re-run.
#   ./setup.sh [pi|qwen|crush|opencode|claude|omp]   (omit to be prompted with a menu)
#   ./setup.sh --pipeline                        (apply config/pipeline.yaml: toggle agents on/off)
#   ./setup.sh --plugin-mirror                   (mirror .claude/* to plugin-root layout)
#   ./setup.sh --check                           (just run the verifier)
#   ./setup.sh --list-installed                  (show what setup has written, from the manifest)
#   ./setup.sh --uninstall [agent]               (restore backups / remove created files; .env is kept)
#
# Every file setup writes outside the working copy (e.g. pi's ~/.pi/agent/*) is backed up first and
# recorded in a manifest, so --uninstall can put your machine back the way it was. State lives in
# ${SDLC_KIT_STATE_DIR:-$HOME/.open-model-sdlc-kit}.
set -euo pipefail
KIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$KIT_DIR"

bold() { printf '\033[1m%s\033[0m\n' "$1"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$1"; }
info() { printf '  • %s\n' "$1"; }
have() { command -v "$1" >/dev/null 2>&1; }

# --- install tracking (backup + uninstall) -------------------------------------
STATE_DIR="${SDLC_KIT_STATE_DIR:-$HOME/.open-model-sdlc-kit}"
MANIFEST="$STATE_DIR/manifest.tsv"
RUN_ID="$(date -u +%Y%m%d-%H%M%S)-$$"   # PID suffix: unique even when re-run within the same second
BACKUP_DIR="$STATE_DIR/backups/$RUN_ID"
AGENT=""   # set during agent selection; used to tag manifest rows

abspath() { case "$1" in /*) printf '%s' "$1" ;; *) printf '%s/%s' "$PWD" "${1#./}" ;; esac; }
# record KIND TARGET [EXTRA] — append one tab-separated row to the manifest.
record() {
  mkdir -p "$STATE_DIR"
  printf '%s\t%s\t%s\t%s\t%s\n' "$RUN_ID" "${AGENT:-kit}" "$1" "$2" "${3:--}" >> "$MANIFEST"
}
# track_copy SRC DST — back up DST if it exists, copy SRC→DST, record the action for --uninstall.
track_copy() {
  local src="$1" dst; dst="$(abspath "$2")"
  mkdir -p "$(dirname "$dst")"
  if [ -e "$dst" ]; then
    local bk="$BACKUP_DIR$dst"; mkdir -p "$(dirname "$bk")"; cp -p "$dst" "$bk"
    record overwritten "$dst" "$bk"
  else
    record created "$dst" -
  fi
  cp -p "$src" "$dst"
}
# track_created PATH — record a file produced by a generator (no source to copy), for --uninstall.
track_created() { record created "$(abspath "$1")" -; }

list_installed() {
  if [ ! -f "$MANIFEST" ]; then info "no installs recorded yet ($MANIFEST absent)"; return 0; fi
  bold "Recorded installs ($MANIFEST)"
  while IFS=$'\t' read -r ts agent kind target _; do
    printf '  [%s] %-8s %-12s %s\n' "$ts" "$agent" "$kind" "$target"
  done < "$MANIFEST"
}

uninstall() {
  local only="${1:-}"
  if [ ! -f "$MANIFEST" ]; then warn "nothing to uninstall ($MANIFEST absent)"; return 0; fi
  bold "Uninstalling${only:+ (agent: $only)} — restoring backups / removing created files"
  local -a rows=() kept=() cleanup_dirs=()
  local line ts agent kind target extra i d
  while IFS= read -r line; do rows+=("$line"); done < "$MANIFEST"
  # Keep rows for non-targeted agents, in original order.
  for ((i = 0; i < ${#rows[@]}; i++)); do
    IFS=$'\t' read -r ts agent kind target extra <<< "${rows[i]}"
    if [ -n "$only" ] && [ "$agent" != "$only" ]; then kept+=("${rows[i]}"); fi
  done
  # Revert in REVERSE order — undo the most recent action first, unwinding the backup stack so a
  # re-run's "overwritten" restore happens before the original "created" removal.
  for ((i = ${#rows[@]} - 1; i >= 0; i--)); do
    IFS=$'\t' read -r ts agent kind target extra <<< "${rows[i]}"
    if [ -n "$only" ] && [ "$agent" != "$only" ]; then continue; fi
    case "$kind" in
      overwritten)
        if [ -f "$extra" ]; then mkdir -p "$(dirname "$target")"; cp -p "$extra" "$target"; ok "restored $target"
        else warn "backup missing for $target ($extra) — left as-is"; fi ;;
      created)
        if [ -e "$target" ]; then rm -f "$target" && ok "removed $target"; fi
        cleanup_dirs+=("$(dirname "$target")") ;;
      hookspath)
        if [ "$extra" = "__none__" ]; then git config --local --unset core.hooksPath 2>/dev/null || true
        else git config --local core.hooksPath "$extra" 2>/dev/null || true; fi
        ok "git core.hooksPath reverted" ;;
      pi-package)
        info "pi package left installed: $target  (remove manually if unwanted: pi uninstall ${target#npm:})" ;;
      *) : ;;
    esac
  done
  # Final pass: drop now-empty directories we created (rmdir -p ignores non-empty parents).
  if [ ${#cleanup_dirs[@]} -gt 0 ]; then
    for d in "${cleanup_dirs[@]}"; do rmdir -p "$d" 2>/dev/null || true; done
  fi
  if [ ${#kept[@]} -gt 0 ]; then printf '%s\n' "${kept[@]}" > "$MANIFEST"; else rm -f "$MANIFEST"; fi
  ok "Uninstall complete. (.env is never tracked, so it was left untouched.)"
}

# --- subcommands ---------------------------------------------------------------
case "${1:-}" in
  --check) exec bash "$KIT_DIR/scripts/check-kit.sh" ;;
  --pipeline) exec bash "$KIT_DIR/scripts/apply-pipeline.sh" ;;
  --list-installed) list_installed; exit 0 ;;
  --uninstall) uninstall "${2:-}"; exit 0 ;;
  --plugin-mirror)
    bold "Mirroring .claude/{agents,commands,skills} → plugin-root layout"
    for d in agents commands skills; do
      [ -d ".claude/$d" ] && { rm -rf "./$d"; cp -r ".claude/$d" "./$d"; ok "$d/"; }
    done
    rm -f ./agents/*.md.disabled 2>/dev/null || true   # don't publish toggled-off agents into the plugin
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
for c in uv uvx; do have "$c" && ok "$c" || warn "$c missing — needed for Serena, Atlassian, git & fetch MCP (https://docs.astral.sh/uv/)"; done
have node && ok "node $(node -v)" || warn "node missing — needed for npx MCP servers, pi, Qwen Code (Node 18+)"
have python3 && ok "python3 ($(python3 -V 2>&1 | awk '{print $2}'))" || warn "python3 missing — needed for the pi/opencode subagent porters AND the Claude guard hook's JSON parsing"
have docker && ok "docker (optional — only the local-infra stack; Atlassian MCP runs via uvx)" || info "docker not found — optional; only needed for the local-infra docker-compose stack"
have task && ok "go-task" || warn "go-task missing — the workspace build runner (https://taskfile.dev)"
have gofumpt || warn "gofumpt missing — the format hook will fall back to gofmt (go install mvdan.cc/gofumpt@latest)"

# --- 2. env --------------------------------------------------------------------
bold "2. Environment"
# .env is intentionally NOT tracked in the manifest: it holds your edited secrets, so --uninstall
# must never delete or revert it.
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
  CURRENT_HOOKS="$(git config --local --get core.hooksPath 2>/dev/null || echo __none__)"
  if [ "$CURRENT_HOOKS" != ".githooks" ]; then record hookspath "core.hooksPath" "$CURRENT_HOOKS"; fi
  git config core.hooksPath .githooks && ok "core.hooksPath → .githooks (guardrails enforced on commit)"
else
  warn "not a git repo — run 'git init && git config core.hooksPath .githooks' after adopting the kit"
fi
chmod +x .claude/hooks/*.sh scripts/*.sh 2>/dev/null || true

# --- 5. agent selection --------------------------------------------------------
bold "5. Agent setup"
AGENT="${1:-}"
if [ -z "$AGENT" ]; then
  detect() { have "$1" && printf '\033[32minstalled\033[0m' || printf '\033[33mnot found\033[0m'; }
  echo "  Select the agent to configure (configs are backed up; undo with ./setup.sh --uninstall):"
  printf '    1) pi        — primary open agent, pi.dev              [%b]\n' "$(detect pi)"
  printf '    2) qwen      — Qwen Code, native MCP                   [%b]\n' "$(detect qwen)"
  printf '    3) crush     — Charm Crush                             [%b]\n' "$(detect crush)"
  printf '    4) opencode  — opencode.ai (agents + commands ported)  [%b]\n' "$(detect opencode)"
  printf '    5) claude    — Claude Code, zero extra config          [%b]\n' "$(detect claude)"
  printf '    6) omp       — oh-my-pi (Pi fork), inherits .claude/    [%b]\n' "$(detect omp)"
  read -r -p "  > number or name [1]: " SEL || true; SEL="${SEL:-1}"
  case "$SEL" in
    1|pi) AGENT=pi ;; 2|qwen) AGENT=qwen ;; 3|crush) AGENT=crush ;;
    4|opencode) AGENT=opencode ;; 5|claude) AGENT=claude ;; 6|omp) AGENT=omp ;;
    *) warn "unknown choice '$SEL' — choose 1-6 or pi|qwen|crush|opencode|claude|omp"; exit 1 ;;
  esac
  ok "selected: $AGENT"
fi
# Honor the pipeline toggle (config/pipeline.yaml) before configuring the harness: park any disabled
# agent as <name>.md.disabled so Claude won't discover it and the porters below skip it.
if command -v python3 >/dev/null 2>&1 && [ -f config/pipeline.yaml ]; then
  bash "$KIT_DIR/scripts/apply-pipeline.sh" --reconcile-only || warn "pipeline reconcile skipped"
fi
PI_DIR="${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}"
case "$AGENT" in
  pi)
    PI_BIN="${PI_BIN:-pi}"
    mkdir -p "$PI_DIR/extensions/subagent" "$PI_DIR/agents"
    # core config (backed up + recorded for --uninstall)
    track_copy agents-config/pi/models.json          "$PI_DIR/models.json"
    track_copy agents-config/pi/mcp.json             "$PI_DIR/mcp.json"
    track_copy agents-config/pi/SYSTEM.md            "$PI_DIR/APPEND_SYSTEM.md"
    track_copy agents-config/pi/settings.json        "$PI_DIR/settings.json"
    track_copy agents-config/pi/subagent-config.json "$PI_DIR/extensions/subagent/config.json"
    ok "pi core config → $PI_DIR (models, mcp, settings, APPEND_SYSTEM, subagent config)"
    # specialist subagents — generated from the canonical .claude/agents (pi-subagents format)
    if have python3; then
      if python3 agents-config/pi/port-agents.py "$PI_DIR/agents" >/dev/null 2>&1; then
        pi_n=0; for f in "$PI_DIR"/agents/*.md; do [ -e "$f" ] && { track_created "$f"; pi_n=$((pi_n + 1)); }; done
        ok "$pi_n subagents → $PI_DIR/agents/ (generated from .claude/agents per config/pipeline.yaml)"
      else warn "port-agents.py failed — run: python3 agents-config/pi/port-agents.py $PI_DIR/agents"; fi
    else warn "python3 missing — can't generate pi subagents; run port-agents.py manually"; fi
    # ecosystem packages (auto-register into settings.json on install)
    if have "$PI_BIN"; then
      for p in npm:pi-mcp-adapter@2.10.0 npm:pi-subagents@0.31.0 npm:@pi-vault/pi-plan@0.1.0 npm:pi-patty-bg-tasks@0.2.0; do
        if "$PI_BIN" install "$p" >/dev/null 2>&1; then record pi-package "$p" -; ok "installed $p"; else warn "pi install $p failed — run it manually"; fi
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
    mkdir -p .qwen; track_copy agents-config/qwen/.qwen/settings.json .qwen/settings.json
    [ -f .qwen/.env ] || cp agents-config/qwen/.qwen/.env.example .qwen/.env
    [ -f QWEN.md ] || cp templates/qwen-template.md QWEN.md
    ok "Qwen Code config → ./.qwen (settings.json + .env) + ./QWEN.md shim — edit .qwen/.env for your endpoint"
    # subagents + commands + skills — generated from the canonical .claude/ (Qwen format), honoring
    # config/pipeline.yaml. settings.json (above) already wires the permissions + guard hooks.
    if have python3; then
      if QW_OUT="$(python3 agents-config/qwen/port-to-qwen.py .qwen 2>/dev/null)"; then
        qwen_n=0
        while IFS= read -r f; do [ -n "$f" ] && [ -e "$f" ] && { track_created "$f"; qwen_n=$((qwen_n + 1)); }; done <<< "$QW_OUT"
        ok "$qwen_n agents + commands + skills → ./.qwen/ (generated from .claude/)"
      else warn "port-to-qwen.py failed — run: python3 agents-config/qwen/port-to-qwen.py .qwen"; fi
    else warn "python3 missing — can't generate Qwen agents/commands/skills; run port-to-qwen.py manually"; fi
    info "Start:  qwen   (reads AGENTS.md + .qwen/{settings.json,agents,commands,skills})"
    info "Verify: /agents · /skills · /spec PROJ-1234 — permissions + guard hooks are wired in settings.json" ;;
  crush)
    track_copy agents-config/crush/crush.json ./crush.json
    ok "Crush config → ./crush.json (reads AGENTS.md automatically)"
    info "Start:  set -a; source .env; set +a;  crush" ;;
  opencode)
    track_copy agents-config/opencode/opencode.json ./opencode.json
    ok "opencode config → ./opencode.json"
    # subagents + commands — generated from the canonical .claude/{agents,commands} (opencode format)
    if have python3; then
      if OC_OUT="$(python3 agents-config/opencode/port-to-opencode.py .opencode 2>/dev/null)"; then
        oc_n=0
        while IFS= read -r f; do [ -n "$f" ] && [ -e "$f" ] && { track_created "$f"; oc_n=$((oc_n + 1)); }; done <<< "$OC_OUT"
        ok "$oc_n agents + commands → ./.opencode/ (generated from .claude/)"
      else warn "port-to-opencode.py failed — run: python3 agents-config/opencode/port-to-opencode.py .opencode"; fi
    else warn "python3 missing — can't generate opencode agents/commands; run port-to-opencode.py manually"; fi
    info "Start:  set -a; source .env; set +a;  opencode"
    info "Verify: opencode reads AGENTS.md + ./.opencode/agent/* + ./.opencode/command/*" ;;
  claude)
    ok "Claude Code uses .mcp.json + .claude/ directly — nothing to copy"
    info "Start: run 'claude' here; approve the project MCP servers when prompted (/mcp)." ;;
  omp)
    # oh-my-pi (omp) is a Pi fork that reads the kit NATIVELY: its config discovery scans .claude/
    # (priority 80) + AGENTS.md + .mcp.json (the 'claude' source contributes MCP servers), with a
    # parent-dir walk. So there is nothing to generate or copy — only install the binary; the git
    # hooks were already wired in step 4. See agents-config/omp/README.md.
    if have omp; then
      ok "omp already installed ($(omp --version 2>/dev/null | head -1 || echo present))"
    else
      info "omp not found — installing (Bun → Homebrew → installer script)"
      if have bun && bun install -g @oh-my-pi/pi-coding-agent >/dev/null 2>&1; then
        ok "installed omp via bun (@oh-my-pi/pi-coding-agent)"
      elif have brew && brew install can1357/tap/omp >/dev/null 2>&1; then
        ok "installed omp via Homebrew (can1357/tap/omp)"
      elif curl -fsSL https://omp.sh/install | sh; then
        ok "installed omp via installer script (https://omp.sh/install)"
      else
        warn "could not auto-install omp — install manually:"
        info "  bun install -g @oh-my-pi/pi-coding-agent   (or: brew install can1357/tap/omp)"
      fi
    fi
    [ -f .mcp.json ] && ok ".mcp.json present — omp's 'claude' source inherits these MCP servers" \
                     || warn ".mcp.json missing — omp will start without MCP servers"
    info "omp reads AGENTS.md + .claude/{agents,commands,skills,rules} natively — no generated copies"
    info "Start:  set -a; source .env; set +a;  omp   (then /agents · /skills · /mcp · /docs)"
    info "Details + caveats: agents-config/omp/README.md" ;;
  *) warn "unknown agent '$AGENT' — choose pi|qwen|crush|opencode|claude|omp"; exit 1 ;;
esac

# --- 6. verify -----------------------------------------------------------------
bold "6. Verifying"
bash "$KIT_DIR/scripts/check-kit.sh" || true
echo
[ -f "$MANIFEST" ] && info "install manifest: $MANIFEST  (undo: ./setup.sh --uninstall ${AGENT})"
info "toggle pipeline agents on/off: edit config/pipeline.yaml, then ./setup.sh --pipeline"
bold "Done. Next: fill .env, then drive a ticket through the pipeline (see FLOW.md)."
