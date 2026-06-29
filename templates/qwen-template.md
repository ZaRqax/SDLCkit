# QWEN.md

> Qwen Code context shim. **`AGENTS.md` is the canonical instruction file** — it is loaded alongside
> this file (see `.qwen/settings.json` `context.fileName`). Read it top to bottom before acting; every
> durable rule lives there. This file only adds Qwen-specific pointers — do not duplicate rules here.

## Qwen-specific pointers

- **Phase subagents** live in `.qwen/agents/` (generated from `.claude/agents/` by
  `agents-config/qwen/port-to-qwen.py`, honoring `config/pipeline.yaml`). Qwen auto-delegates to them
  by their `description` — e.g. the planner for a new ticket, the engineer to implement approved tasks.
- **Slash commands** `/spec /clarify /plan /tasks /implement /test /review /pr` live in `.qwen/commands/`.
- **Skills** (reusable runbooks) live in `.qwen/skills/` and auto-load when relevant — e.g.
  `serena-first` (symbol-accurate Go edits) and `requirements-clarify` (turn a vague ask into decided
  questions with proposed answers before designing/coding).
- **Enforcement:** `.qwen/settings.json` wires `permissions` (deny hand-editing generated code —
  `sqlc/`, `mocks/`, `gen/`, `*.pb.go`; deny reading `.env`) and PreToolUse/PostToolUse **hooks**
  (`.claude/hooks/format-and-guard.sh`) that block destructive commands and protected-branch pushes
  mid-session — the same guard Claude uses.
- **Models:** each subagent declares a Qwen selector — `inherit` (the session's strong model) for
  judgment roles (planner/tech-designer/reviewer/devops-lead) and `fast` (your `fastModel`) for
  high-volume roles (engineer/qa-lead/rlm). Set the strong model with `/model` and the fast one with
  `/model --fast`.
- **Autonomy:** for a long self-driven run, use `/goal <done-condition>` — Qwen keeps working until the
  condition holds. Read-only specialists (reviewer, rlm) cannot mutate files (enforced via
  `disallowedTools`).

Per-service detail goes in a **nested `AGENTS.md`** inside the service repo (nearest file wins) — never
fork the root rules.
