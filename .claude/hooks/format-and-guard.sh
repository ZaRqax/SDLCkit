#!/usr/bin/env bash
# format-and-guard.sh — Claude Code hook. The TRUE enforcement layer (CLAUDE.md/AGENTS.md text is
# only context). Reads the hook event JSON from stdin. Mode is $1:
#   pre-edit   PreToolUse(Edit|Write): block edits to generated dirs.
#   pre-bash   PreToolUse(Bash):       block pushes to protected branches.
#   post-edit  PostToolUse(Edit|Write): gofumpt the edited Go file.
# Contract: exit 2 + message on stderr => Claude blocks the tool call.
set -euo pipefail
MODE="${1:-}"
INPUT="$(cat)"

# Extract a field from the tool input JSON without requiring jq.
field() {
  printf '%s' "$INPUT" | python3 -c "import sys,json
d=json.load(sys.stdin)
ti=d.get('tool_input',{}) or {}
print(ti.get('$1','') or '')" 2>/dev/null || true
}

GENERATED_RE='(/repository/postgres/sqlc/|/mocks/|/gen/|\.pb\.go$|_gen\.go$)'

case "$MODE" in
  pre-edit)
    FP="$(field file_path)"
    [ -z "$FP" ] && FP="$(field path)"
    if printf '%s' "$FP" | grep -Eq "$GENERATED_RE"; then
      echo "BLOCKED: '$FP' is generated code. Never hand-edit sqlc/, mocks/, gen/, or *.pb.go." >&2
      echo "Change the SQL / proto / interface and regenerate: task sqlc | task mocks | task gen." >&2
      exit 2
    fi
    ;;
  pre-bash)
    CMD="$(field command)"
    if printf '%s' "$CMD" | grep -Eq 'git[[:space:]]+push'; then
      if printf '%s' "$CMD" | grep -Eq '(main|master|develop|release/)'; then
        echo "BLOCKED: pushing to a protected branch (main/develop/release/*). These need a PR + 2 approvals." >&2
        exit 2
      fi
    fi
    ;;
  post-edit)
    FP="$(field file_path)"
    [ -z "$FP" ] && FP="$(field path)"
    if printf '%s' "$FP" | grep -Eq '\.go$' && ! printf '%s' "$FP" | grep -Eq "$GENERATED_RE"; then
      if command -v gofumpt >/dev/null 2>&1; then gofumpt -w "$FP" >/dev/null 2>&1 || true
      elif command -v gofmt   >/dev/null 2>&1; then gofmt   -w "$FP" >/dev/null 2>&1 || true; fi
    fi
    ;;
esac
exit 0
