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
- `go-code-reviewer` — phase 7: a multi-pass, verification-first Go review (correctness/concurrency,
  SOLID/DRY/KISS/YAGNI, idioms, security, tests/AC, spec↔code drift) with severity+confidence scoring,
  self-refutation to kill false positives, and an inline customizable `PROJECT-SPECIFIC RULES` block.
- `devops-lead` — Taskfile / Docker / Helm / CI concerns.
- `rlm` — **utility, not a pipeline phase**: a Recursive Language Model solver for a too-big task —
  decompose → delegate to fresh sub-solvers → aggregate (read-only). See Workflows below.

Which subagents are active is governed by `config/pipeline.yaml` — set `enabled: false` and run
`./setup.sh --pipeline` to drop one (e.g. `devops-lead`) from this list and every other harness.

## Commands (`.claude/commands/`)
`/spec`, `/clarify`, `/plan`, `/tasks`, `/implement`, `/test`, `/review`, `/pr` — one per phase (§2).
Plus `/rlm <task>` — the recursive solver (utility, any time). They also work as plain runbooks for
non-Claude agents.

## Workflows (`.claude/workflows/`)
- `rlm` — the genuine bounded-recursion engine behind `/rlm`: `Workflow({name:"rlm", args:{task, maxDepth, fanout}})`
  spawns one fresh `agent()` per node, parallel children, with depth/fanout/budget rails in code. This
  is the reliable recursion path under Claude Code (a plain `.claude/agents/*` can't spawn subagents).

## Skills (`.claude/skills/`)
`serena-first`, `precommit`, `go-grpc-handler`, `sqlc-migration`, `testify-suite`, `test-debug-loop`,
`codebase-onboarding`, `rlm-recursive`, `commit-message`, `jira-flow` — auto-load by description, or
invoke as `/<skill-name>`.

## Enforcement
Hard guardrails are **enforced**, not just suggested, for Claude:
- `.claude/settings.json` — `permissions.deny` blocks edits to generated dirs and reads of `.env`;
  `permissionMode` asks before DB migrations and pushes.
- `.claude/hooks/format-and-guard.sh` — `PreToolUse` blocks edits to `sqlc/`,`mocks/`,`gen/`, pushes
  to protected branches, and the destructive commands in `config/security-policy.yaml` (`rm -rf /`,
  force-push, `DROP DATABASE`, `terraform destroy`); `PostToolUse` runs gofumpt on edited Go files.

Open agents (pi/Qwen/Crush) have no hook layer, so the **same** guardrails also live in
`.githooks/pre-commit` + CI. Keep both in sync.

## Plan mode
For multi-file or cross-service work, use plan mode first — it maps cleanly onto phases 1–4 (spec →
clarify → plan → tasks). Get the `tasks.md` approved before implementing.
