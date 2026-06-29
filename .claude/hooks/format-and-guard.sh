#!/usr/bin/env bash
# format-and-guard.sh — shared tool-guard hook for Claude Code AND Qwen Code (both use the same
# PreToolUse/PostToolUse JSON-on-stdin, exit-2-to-block contract; Qwen's tool ids edit/write_file/
# run_shell_command carry the same tool_input.file_path / tool_input.command fields). It is the TRUE
# enforcement layer (CLAUDE.md/AGENTS.md text is only context). Reads the hook event JSON from stdin.
# Mode is $1:
#   pre-edit   PreToolUse(edit|write_file): block edits to generated dirs.
#   pre-bash   PreToolUse(run_shell_command): block destructive cmds / pushes to protected branches.
#   post-edit  PostToolUse(edit|write_file): gofumpt the edited Go file.
# Contract: exit 2 + message on stderr => the agent blocks the tool call.
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
    # Hard-block destructive commands (canonical list: config/security-policy.yaml `shell.blocked`).
    # rm with recursive+force flags targeting / /* ~ $HOME, or --no-preserve-root — filesystem wipes.
    # Narrow target match so 'rm -rf ./build', 'rm -rf /tmp/x', 'rm -rf ~/.cache' are NOT blocked.
    if printf '%s' "$CMD" | grep -Eq 'no-preserve-root' \
       || { printf '%s' "$CMD" | grep -Eq '(^|[[:space:];&|(])rm([[:space:]]|$)' \
            && printf '%s' "$CMD" | grep -Eq -- '-[A-Za-z]*[rR]' \
            && printf '%s' "$CMD" | grep -Eq -- '-[A-Za-z]*[fF]' \
            && printf '%s' "$CMD" | grep -Eq '[[:space:]]/([[:space:]*;&|]|$)|[[:space:]](~|\$HOME|\$\{HOME\})([[:space:];&|]|$)'; }; then
      echo "BLOCKED: refusing 'rm -rf' against / ~ \$HOME (filesystem wipe). See config/security-policy.yaml." >&2
      exit 2
    fi
    # force-push rewrites shared history — never from an agent (any branch).
    if printf '%s' "$CMD" | grep -Eq 'git[[:space:]]+push' \
       && printf '%s' "$CMD" | grep -Eq '(--force([^-]|$)|--force-with-lease|[[:space:]]-f([[:space:]]|$))'; then
      echo "BLOCKED: force-push rewrites shared history. Open a PR instead. See config/security-policy.yaml." >&2
      exit 2
    fi
    # Destructive raw SQL — schema changes must go through migrations (task db:migrate).
    if printf '%s' "$CMD" | grep -Eqi 'drop[[:space:]]+(database|schema)'; then
      echo "BLOCKED: destructive raw SQL (DROP DATABASE/SCHEMA). Use a migration: task db:migrate:create." >&2
      exit 2
    fi
    # Tearing down infrastructure.
    if printf '%s' "$CMD" | grep -Eq 'terraform[[:space:]]+destroy'; then
      echo "BLOCKED: 'terraform destroy' tears down infrastructure. See config/security-policy.yaml." >&2
      exit 2
    fi
    # Push to a protected branch — needs a PR + 2 approvals.
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
