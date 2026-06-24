@AGENTS.md

# Claude Code — kit-specific notes

The full, canonical instructions are imported from `AGENTS.md` above (single source of truth, shared
with pi / Qwen Code / Crush / opencode). This section adds only the Claude-Code-specific extras.

## Subagents (`.claude/agents/`)
Delegate phases to the specialist subagents — Claude auto-selects by their `description`, or invoke
explicitly:
- `planner` — phase 1–2: read the Jira ticket, write `spec.md`, decompose into stories.
- `tech-designer` — phase 3: write `plan.md` (architecture, data model, contracts).
- `engineer` — phase 5: implement one task at a time with Serena symbol edits.
- `qa-lead` — phase 6: write `test-plan.md` + testify suites.
- `go-code-reviewer` — phase 7: review the diff for clean-arch / partial-struct / lint violations.
- `devops-lead` — Taskfile / Docker / Helm / CI concerns.

## Commands (`.claude/commands/`)
`/spec`, `/clarify`, `/plan`, `/tasks`, `/implement`, `/test`, `/review`, `/pr` — one per phase (§2).
They also work as plain runbooks for non-Claude agents.

## Skills (`.claude/skills/`)
`serena-first`, `precommit`, `go-grpc-handler`, `sqlc-migration`, `testify-suite`, `commit-message`,
`jira-flow` — auto-load by description, or invoke as `/<skill-name>`.

## Enforcement
Hard guardrails are **enforced**, not just suggested, for Claude:
- `.claude/settings.json` — `permissions.deny` blocks edits to generated dirs and reads of `.env`;
  `permissionMode` asks before DB migrations and pushes.
- `.claude/hooks/format-and-guard.sh` — `PreToolUse` blocks edits to `sqlc/`,`mocks/`,`gen/` and
  pushes to protected branches; `PostToolUse` runs gofumpt on edited Go files.

Open agents (pi/Qwen/Crush) have no hook layer, so the **same** guardrails also live in
`.githooks/pre-commit` + CI. Keep both in sync.

## Plan mode
For multi-file or cross-service work, use plan mode first — it maps cleanly onto phases 1–4 (spec →
clarify → plan → tasks). Get the `tasks.md` approved before implementing.
