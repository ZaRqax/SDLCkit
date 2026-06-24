#!/usr/bin/env bash
# check-kit.sh — verify the kit is well-formed and (optionally) that its MCP servers can start.
#   ./scripts/check-kit.sh           structural checks
#   ./scripts/check-kit.sh --mcp     also probe that Serena/Atlassian deps are runnable
set -uo pipefail
KIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$KIT_DIR"
fail=0
ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; }
bad()  { printf '  \033[31m✗\033[0m %s\n' "$1"; fail=1; }
warn() { printf '  \033[33m!\033[0m %s\n' "$1"; }

printf '\033[1mStructure\033[0m\n'
for f in AGENTS.md CLAUDE.md README.md INSTALL.md FLOW.md .mcp.json mcp.example.json .env.example \
         setup.sh .githooks/pre-commit .claude/settings.json .claude/hooks/format-and-guard.sh \
         templates/spec-template.md templates/plan-template.md templates/tasks-template.md \
         templates/pr-template.md templates/handoff-template.md agents-config/sampling-params.md \
         agents-config/pi/settings.json agents-config/pi/subagent-config.json \
         agents-config/pi/port-agents.py agents-config/pi/README.md; do
  [ -f "$f" ] && ok "$f" || bad "missing $f"
done

head -1 CLAUDE.md | grep -q '@AGENTS.md' && ok "CLAUDE.md imports AGENTS.md" || bad "CLAUDE.md missing @AGENTS.md on line 1"

printf '\033[1mComponents\033[0m\n'
count() { find "$1" -name "$2" 2>/dev/null | wc -l | tr -d ' '; }
a=$(count .claude/agents '*.md');   [ "$a" -ge 6 ] && ok "$a subagents"     || bad "expected ≥6 subagents, found $a"
c=$(count .claude/commands '*.md'); [ "$c" -ge 8 ] && ok "$c commands"      || bad "expected ≥8 commands, found $c"
s=$(find .claude/skills -name SKILL.md 2>/dev/null | wc -l | tr -d ' '); [ "$s" -ge 7 ] && ok "$s skills" || bad "expected ≥7 skills, found $s"

printf '\033[1mJSON validity\033[0m\n'
jsoncheck() {
  if command -v python3 >/dev/null 2>&1; then
    python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$1" 2>/dev/null && ok "valid JSON: $1" || bad "INVALID JSON: $1"
  else warn "python3 absent — skipped JSON check for $1"; fi
}
for j in .mcp.json mcp.example.json .claude/settings.json handoff/schema.json \
         .claude-plugin/plugin.json .claude-plugin/marketplace.json \
         agents-config/pi/models.json agents-config/pi/mcp.json \
         agents-config/pi/settings.json agents-config/pi/subagent-config.json \
         agents-config/qwen/.qwen/settings.json agents-config/crush/crush.json \
         agents-config/opencode/opencode.json; do
  [ -f "$j" ] && jsoncheck "$j"
done

printf '\033[1mFrontmatter\033[0m\n'
for f in .claude/agents/*.md; do
  head -1 "$f" | grep -q '^---$' && grep -q '^name:' "$f" || bad "frontmatter issue in $f"
done
[ "$fail" -eq 0 ] && ok "all subagent frontmatter present"

printf '\033[1mNo Cyrillic in shipped configs/instructions\033[0m\n'
if grep -rlP '[\x{0400}-\x{04FF}]' AGENTS.md CLAUDE.md .claude templates agents-config 2>/dev/null | grep -q .; then
  bad "Cyrillic found in a kit file (code/instructions must be English)"
else ok "English-only"; fi

printf '\033[1mpi setup\033[0m\n'
if command -v python3 >/dev/null 2>&1; then
  python3 -c "import py_compile; py_compile.compile('agents-config/pi/port-agents.py', doraise=True)" 2>/dev/null \
    && ok "port-agents.py compiles" || bad "port-agents.py has a syntax error"
else warn "python3 absent — skipped port-agents.py check"; fi
grep -q 'pi-mcp-adapter' agents-config/pi/settings.json 2>/dev/null && ok "pi-mcp-adapter declared in settings.json" || bad "pi-mcp-adapter missing from agents-config/pi/settings.json"
pa=$(find agents-config/pi/agents -name '*.md' 2>/dev/null | wc -l | tr -d ' ')
[ "$pa" -ge 6 ] && ok "$pa pi subagents generated" || warn "pi subagents not generated ($pa) — run: python3 agents-config/pi/port-agents.py"

if [ "${1:-}" = "--mcp" ]; then
  printf '\033[1mMCP runnable (probe)\033[0m\n'
  command -v uvx >/dev/null 2>&1 && ok "uvx present (serena/git/fetch)" || bad "uvx missing"
  command -v docker >/dev/null 2>&1 && ok "docker present (atlassian)" || warn "docker missing (atlassian MCP)"
  command -v npx >/dev/null 2>&1 && ok "npx present (context7/sequential-thinking)" || warn "npx missing"
fi

echo
[ "$fail" -eq 0 ] && printf '\033[32mKit OK\033[0m\n' || printf '\033[31mKit has issues (see ✗ above)\033[0m\n'
exit "$fail"
