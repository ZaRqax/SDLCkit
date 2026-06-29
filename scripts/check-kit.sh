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
         config/security-policy.yaml config/pipeline.yaml \
         scripts/pipeline_config.py scripts/apply-pipeline.sh \
         templates/spec-template.md templates/plan-template.md templates/tasks-template.md \
         templates/pr-template.md templates/handoff-template.md templates/qwen-template.md \
         agents-config/sampling-params.md \
         agents-config/pi/settings.json agents-config/pi/subagent-config.json \
         agents-config/pi/port-agents.py agents-config/pi/README.md \
         agents-config/opencode/opencode.json agents-config/opencode/port-to-opencode.py \
         agents-config/qwen/port-to-qwen.py \
         agents-config/omp/README.md \
         .claude/workflows/rlm.js; do
  [ -f "$f" ] && ok "$f" || bad "missing $f"
done

head -1 CLAUDE.md | grep -q '@AGENTS.md' && ok "CLAUDE.md imports AGENTS.md" || bad "CLAUDE.md missing @AGENTS.md on line 1"

printf '\033[1mComponents\033[0m\n'
count() { find "$1" -name "$2" 2>/dev/null | wc -l | tr -d ' '; }
# Compile the shared pipeline parser first, so a parser bug is reported AS a parser bug (not later
# mis-attributed to config/pipeline.yaml being "invalid").
if command -v python3 >/dev/null 2>&1; then
  python3 -c "import py_compile; py_compile.compile('scripts/pipeline_config.py', doraise=True)" 2>/dev/null \
    && ok "pipeline_config.py compiles" || bad "pipeline_config.py has a syntax error"
fi
# The active subagent set is governed by config/pipeline.yaml (the pipeline toggle). Disabled agents
# are parked as <name>.md.disabled, so the active count must equal the config's enabled count.
a=$(count .claude/agents '*.md')
exp=""   # enabled count from the config; reused by the pi-snapshot check below
if command -v python3 >/dev/null 2>&1 && [ -f config/pipeline.yaml ]; then
  exp="$(python3 scripts/pipeline_config.py expected-count 2>/dev/null || true)"
  if [ -n "$exp" ]; then
    [ "$a" -eq "$exp" ] && ok "$a active subagents (config/pipeline.yaml enables $exp)" \
      || bad "$a active subagents, but config/pipeline.yaml enables $exp — run ./setup.sh --pipeline"
  else
    [ "$a" -ge 5 ] && ok "$a subagents" || bad "expected ≥5 subagents, found $a"
  fi
  pc_msgs="$(python3 scripts/pipeline_config.py check 2>&1 1>/dev/null)"; pc_rc=$?
  [ "$pc_rc" -eq 0 ] && ok "config/pipeline.yaml valid" \
    || bad "config/pipeline.yaml invalid (run: python3 scripts/pipeline_config.py check)"
  while IFS= read -r m; do [ -n "$m" ] && warn "${m#*: }"; done <<EOF
$pc_msgs
EOF
  for e in $(python3 scripts/pipeline_config.py enabled 2>/dev/null); do
    [ -f ".claude/agents/$e.md" ] || bad "$e enabled in config but .claude/agents/$e.md is missing"
  done
  for d in $(python3 scripts/pipeline_config.py disabled 2>/dev/null); do
    [ -f ".claude/agents/$d.md" ] && warn "$d disabled in config but .claude/agents/$d.md is still active — run ./setup.sh --pipeline"
  done
  for f in .claude/agents/*.md; do [ -e "$f" ] || continue; n="$(basename "$f" .md)"
    python3 scripts/pipeline_config.py names 2>/dev/null | grep -qx "$n" \
      || warn "$n has no entry in config/pipeline.yaml (add it so the toggle can manage it)"; done
else
  [ "$a" -ge 5 ] && ok "$a subagents" || bad "expected ≥5 subagents, found $a"
fi
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
# Use python3, not `grep -P`: PCRE grep is unavailable on macOS/BSD grep. python3 is a kit prereq.
if command -v python3 >/dev/null 2>&1; then
  CY="$(python3 - AGENTS.md CLAUDE.md .claude templates agents-config config <<'PY'
import os, re, sys
pat = re.compile(r"[Ѐ-ӿ]")
hits = []
for root in sys.argv[1:]:
    files = [root] if os.path.isfile(root) else [
        os.path.join(d, f) for d, _, fs in os.walk(root) for f in fs]
    for fp in files:
        try:
            with open(fp, encoding="utf-8", errors="ignore") as fh:
                if pat.search(fh.read()):
                    hits.append(fp)
        except OSError:
            pass
print("\n".join(hits))
PY
)"
  [ -z "$CY" ] && ok "English-only" || bad "Cyrillic found in: $(printf '%s' "$CY" | tr '\n' ' ')"
else warn "python3 absent — skipped Cyrillic check"; fi

printf '\033[1mpi setup\033[0m\n'
if command -v python3 >/dev/null 2>&1; then
  python3 -c "import py_compile; py_compile.compile('agents-config/pi/port-agents.py', doraise=True)" 2>/dev/null \
    && ok "port-agents.py compiles" || bad "port-agents.py has a syntax error"
else warn "python3 absent — skipped port-agents.py check"; fi
grep -q 'pi-mcp-adapter' agents-config/pi/settings.json 2>/dev/null && ok "pi-mcp-adapter declared in settings.json" || bad "pi-mcp-adapter missing from agents-config/pi/settings.json"
pa=$(find agents-config/pi/agents -name '*.md' 2>/dev/null | wc -l | tr -d ' ')
if [ -n "$exp" ]; then
  [ "$pa" -eq "$exp" ] && ok "$pa pi subagents generated (matches $exp enabled)" \
    || warn "pi snapshot has $pa agents but config enables $exp — run: python3 agents-config/pi/port-agents.py"
else
  [ "$pa" -ge 5 ] && ok "$pa pi subagents generated" || warn "pi subagents not generated ($pa) — run: python3 agents-config/pi/port-agents.py"
fi

printf '\033[1mopencode setup\033[0m\n'
if command -v python3 >/dev/null 2>&1; then
  python3 -c "import py_compile; py_compile.compile('agents-config/opencode/port-to-opencode.py', doraise=True)" 2>/dev/null \
    && ok "port-to-opencode.py compiles" || bad "port-to-opencode.py has a syntax error"
else warn "python3 absent — skipped port-to-opencode.py check"; fi

printf '\033[1mqwen setup\033[0m\n'
if command -v python3 >/dev/null 2>&1; then
  python3 -c "import py_compile; py_compile.compile('agents-config/qwen/port-to-qwen.py', doraise=True)" 2>/dev/null \
    && ok "port-to-qwen.py compiles" || bad "port-to-qwen.py has a syntax error"
else warn "python3 absent — skipped port-to-qwen.py check"; fi
# Qwen agents/commands/skills are generated into the gitignored .qwen/ by setup.sh. Only check parity
# when Qwen has been set up (.qwen/agents exists); otherwise it is simply not installed yet.
if [ -d .qwen/agents ]; then
  qa=$(find .qwen/agents -name '*.md' 2>/dev/null | wc -l | tr -d ' ')
  if [ -n "$exp" ]; then
    [ "$qa" -eq "$exp" ] && ok "$qa qwen subagents generated (matches $exp enabled)" \
      || warn "qwen has $qa agents but config enables $exp — run: python3 agents-config/qwen/port-to-qwen.py .qwen"
  else
    [ "$qa" -ge 5 ] && ok "$qa qwen subagents generated" || warn "qwen subagents low ($qa) — run port-to-qwen.py"
  fi
fi

printf '\033[1momp setup\033[0m\n'
# oh-my-pi (omp) reads .claude/{agents,commands,skills,rules} + AGENTS.md + .mcp.json NATIVELY (its
# config discovery scans the .claude source), so there is no porter and no generated-copy parity to
# check — only confirm the harness doc is shipped (Structure above) and note the inheritance.
printf '  \033[2m· omp inherits .claude/ + AGENTS.md + .mcp.json natively — no porter; see agents-config/omp/README.md\033[0m\n'

printf '\033[1mworkflows\033[0m\n'
if command -v node >/dev/null 2>&1; then
  # Parse (not run) the rlm workflow: strip `export`, wrap the body in an async fn so the harness's
  # top-level await/return are legal, and let `new Function` validate the syntax.
  node -e 'const fs=require("fs");const s=fs.readFileSync(".claude/workflows/rlm.js","utf8").replace(/^export\s+const\s+meta/m,"const meta");new Function("args","budget","agent","parallel","pipeline","phase","log","return (async()=>{"+s+"\n})()")' 2>/dev/null \
    && ok "rlm workflow parses" || bad "rlm workflow has a syntax error"
else warn "node absent — skipped workflow parse check"; fi

if [ "${1:-}" = "--mcp" ]; then
  printf '\033[1mMCP runnable (probe)\033[0m\n'
  command -v uvx >/dev/null 2>&1 && ok "uvx present (serena/atlassian/git/fetch)" || bad "uvx missing"
  command -v npx >/dev/null 2>&1 && ok "npx present (context7/sequential-thinking)" || warn "npx missing"
  command -v docker >/dev/null 2>&1 && ok "docker present (optional — local-infra stack only)" || warn "docker missing (optional — local-infra stack only)"
fi

echo
[ "$fail" -eq 0 ] && printf '\033[32mKit OK\033[0m\n' || printf '\033[31mKit has issues (see ✗ above)\033[0m\n'
exit "$fail"
