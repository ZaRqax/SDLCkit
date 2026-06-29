# KIT-DEV.md — how this kit is built & maintained (canonical facts)

This is the source-of-truth for kit authors and for any agent generating kit files. Keep every
component consistent with the decisions below.

## What the kit is
A **stand-alone, open-model-first SDLC harness** for the Acme Go-microservices workspace.
Its purpose is to make a *lightweight open model* (GLM-5.1, Qwen3-Coder-Next) write high-quality code
by giving it **more explicit structure + stronger tools**, while running unchanged under Claude Code.

## Locked decisions
- **One source, many harnesses.** All durable guidance lives once in root `AGENTS.md`. `CLAUDE.md` is a
  `@AGENTS.md` shim + a small Claude-only section. Per-service detail goes in nested `AGENTS.md`
  (nearest-file-wins), never duplicated into CLAUDE.md.
- **Primary agent = pi (pi.dev).** pi ships only read/write/edit/bash; capability comes from pi
  **packages** (declared in `agents-config/pi/settings.json` → `packages[]`). Secondary agents:
  Qwen Code (native MCP), Crush, opencode, omp (oh-my-pi).
- **opencode = first-class secondary.** Like pi, its subagents + commands are GENERATED from the
  single source `.claude/{agents,commands}` by `agents-config/opencode/port-to-opencode.py` into
  `.opencode/{agent,command}/*.md` (`mode: subagent`; tools mapped with read-only parity for the
  reviewer; `$1`→`$ARGUMENTS`; model inherited from `opencode.json`, never hardcoded; skills appended
  as a body footer since opencode won't auto-load them). `setup.sh opencode` runs it. Generated
  `.opencode/`, `opencode.json`, `crush.json`, `.qwen/` are gitignored — regenerate, don't commit.
- **omp (oh-my-pi) = native inheritance, no porter.** omp is a Pi fork whose config discovery scans
  `.omp` (100) > `.claude` (80) > `.codex` (70) > `.gemini` (60) at user + project level, walking parent
  dirs; the `claude` source (on by default) contributes context files, MCP servers, commands, skills,
  hooks, tools, and settings. So the kit's `AGENTS.md` + `.claude/{agents,commands,skills,rules}` +
  `.mcp.json` work in omp with **zero generated copies** — `setup.sh omp` only installs the binary
  (Bun → Homebrew → installer) and wires git hooks. `agents-config/omp/README.md` documents it; `/.omp/`
  is gitignored (only needed for optional omp-native overrides). Do NOT set `disabledProviders: [claude]`.
- **pi package set (default):** `pi-mcp-adapter` (MCP — pi has no native MCP, so this package bridges
  the servers declared in `agents-config/pi/mcp.json`), `pi-subagents`
  (subagents — generated from `.claude/agents/` by `agents-config/pi/port-agents.py` into
  `~/.pi/agent/agents/`; `agents-config/pi/agents/*.md` is GENERATED, don't hand-edit), `@pi-vault/pi-plan`
  (read-only plan-mode guardrail), `pi-patty-bg-tasks` (background test/lint jobs). The adapter reads
  `agents-config/pi/mcp.json` (`directTools` promote hot Serena tools; `lazy` lifecycle elsewhere). Optional/off by default: `@geminixiang/pi-diff`, `pi-web-access`,
  `rpiv-ask-user-question`, `pi-permission-system`, `pi-hypa`. Rejected: `pi-lens` (overlaps Serena +
  gofumpt), memory packages (overlap `.serena/memories`), `rpiv-todo` (overlaps `tasks.md`). Versions pinned & verified vs the npm registry 2026-06-24
(adapter 2.10.0, subagents 0.31.0, pi-plan 0.1.0, bg-tasks 0.2.0, pi CLI 0.80.2); `@pi-vault/pi-plan`
needs Node ≥24.15.0.
- **Co-primary models = GLM-5.1 + Qwen3-Coder-Next**, served over an OpenAI-compatible `/v1` endpoint.
  Sampling pinned in `agents-config/sampling-params.md`.
- **Code intelligence = Serena** (uvx-from-git, over gopls). Mandated over whole-file reads/edits.
  Commit `.serena/memories` + `.serena/project.yml`; gitignore `.serena/cache`. Needs `GITHUB_PAT`
  so gopls can index private `github.com/acme` modules.
- **Jira/Confluence = sooperset/mcp-atlassian, run via `uvx mcp-atlassian`** (a local process, NOT
  Docker — the container variant spawned orphaned containers that were never reaped). Default profile is **READ-WRITE via a
  service account**, scoped to `JIRA_PROJECTS_FILTER=PROJ,TEAM`. A read-only profile is one env var away
  (`ATLASSIAN_READ_ONLY=true`). Official Atlassian Remote MCP documented as the Cloud/OAuth alternative.
- **Core MCP set** (`.mcp.json`): serena, atlassian, context7, sequential-thinking, git, fetch.
  **Optional** (in `mcp.example.json`): filesystem (core for open agents), postgres-mcp-pro (restricted),
  playwright (UI repos), official github. **Banned:** `@modelcontextprotocol/server-postgres` (CVE) and
  `@modelcontextprotocol/server-github` (archived).
- **Enforcement is layered:** prose+examples (AGENTS.md) → Claude `settings.json` permissions + hooks →
  open-agent fallback in `.githooks/pre-commit` + CI. Text is context; hooks/CI are enforcement.
- **Safety policy = `config/security-policy.yaml`** (adapted from pi-sdlc-kit): the human-readable
  source of truth for blocked/confirm shell commands, secrets, and generated-code rules. The
  `pre-bash` hook hard-blocks `shell.blocked` (`rm -rf /`·`~`·`$HOME`, force-push, `DROP DATABASE`,
  `terraform destroy`); `settings.json` `ask` covers `shell.confirm` (kubectl delete, terraform apply,
  git reset --hard, …); AGENTS.md §8 mirrors it for open agents. Keep the three in sync.
- **Optional, NOT core:** the heavy spec↔code graph/drift engine (documented in `docs/optional-graph-engine.md`).
- **RLM (recursive solver) = a utility, not a pipeline phase.** Implements *Recursive Language Models*
  (Zhang, Kraska, Khattab, arXiv:2512.24601): decompose a too-big task/context → delegate each
  independent piece to a fresh sub-solver → aggregate, with hard rails (max depth 3, fanout 5, budget,
  base-case, independence). **Read-only** (analysis/understanding at scale, NOT parallel code edits).
  Single source: `.claude/agents/rlm.md` + `.claude/commands/rlm.md` + skill `rlm-recursive`
  (auto-ported to pi/opencode like every agent/command). Genuine recursion under Claude Code is the
  `.claude/workflows/rlm.js` engine (recursive `agent()` per node); plain subagents can't self-spawn,
  so other harnesses delegate via `/run rlm` (pi) / `task(rlm,…)` (opencode) or run the runbook by hand.
- **Pipeline roster = `config/pipeline.yaml`** (single source of truth for *which* agents are active).
  Each agent has `role` (`core-phase` | `specialist` | `utility`), `phases`, `commands`, `enabled`.
  Toggling is enforced from one place: `scripts/pipeline_config.py` (a tiny stdlib YAML-subset reader,
  no PyYAML) is imported by both porters (skip disabled agents + commands) and shelled to by
  `check-kit.sh` (derives the expected count) and `scripts/apply-pipeline.sh` (parks `<name>.md` ↔
  `<name>.md.disabled` so Claude stops discovering it, re-ports, re-verifies). `./setup.sh --pipeline`
  is the entry point. Fail-open: a missing/broken config ports everything. Commands stay in
  `.claude/commands/` (they double as runbooks); only opencode drops a command orphaned by a disabled
  agent. See the section below.
- **`go-code-reviewer` = the kit's deepest agent.** A multi-pass, verification-first Go reviewer
  (correctness/concurrency → SOLID/DRY/KISS/YAGNI/clean-arch → idioms → security → tests/AC → drift)
  that scores severity+confidence and self-refutes to suppress false positives. Its team-specific rules
  live INLINE between `<!-- BEGIN/END PROJECT RULES -->` markers (so the porters carry them verbatim to
  pi/opencode) — that block is the customization point; the passes around it are universal.

## The pipeline (phase → command → agent → artifact)
| Phase | Command | Claude subagent | Artifact (in `specs/<TASK_ID>-<slug>/`) |
|---|---|---|---|
| 1 spec | `/spec` | planner | `spec.md` |
| 2 clarify | `/clarify` | planner | open-questions resolved in `spec.md` |
| 3 plan | `/plan` | tech-designer | `plan.md` |
| 4 tasks | `/tasks` | tech-designer | `tasks.md` (`[P]` markers, AC-traceable, story files) |
| 5 implement | `/implement` | engineer | code (one task at a time, Serena edits) |
| 6 test | `/test` | qa-lead | `test-plan.md` + green `task lint`/`task test` |
| 7 review | `/review` | go-code-reviewer | review notes; spec↔plan↔tasks↔code cross-check |
| 8 pr | `/pr` | (engineer) | `[WIP] [TASK_ID]` PR from `templates/pr-template.md` |

## Pipeline configuration (toggle agents on/off)
`config/pipeline.yaml` decides which agents exist in the pipeline. To drop one (the common case:
`devops-lead` when there's no infra work, or `rlm`):

```yaml
agents:
  devops-lead:
    role: specialist     # core-phase | specialist | utility
    phases: [5]
    commands: []
    enabled: false       # <- the toggle
```
```bash
./setup.sh --pipeline    # or: bash scripts/apply-pipeline.sh
```

What `apply-pipeline.sh` does, in order: (1) validates the config (`pipeline_config.py check`); (2)
reconciles `.claude/agents/` — a disabled agent's `<name>.md` is renamed to `<name>.md.disabled`
(Claude only loads `*.md`, so it disappears from discovery), an enabled one is restored; (3) re-runs
the pi porter into `agents-config/pi/agents/` and (if `.opencode/` exists) the opencode porter, both of
which skip disabled agents and any command bound only to a disabled agent; (4) runs `check-kit.sh`.
`setup.sh <agent>` also calls `--reconcile-only` first, so a normal setup already honors the toggle.

Why this shape:
- **One mechanism, every harness.** Every consumer globs `*.md`, so the `.md.disabled` rename hides a
  disabled agent from Claude, both porters, and the verifier at once. Qwen/Crush read AGENTS.md prose
  only — nothing per-agent to reconcile. omp reads `.claude/agents/*.md` natively, so the same rename
  hides a disabled agent from omp too (its glob also matches `*.md` only).
- **One parser.** `scripts/pipeline_config.py` is the only place the YAML subset is read; the porters
  import it, the shell scripts shell out to it. No duplicated parsing (the kit's anti-drift rule).
- **Fail-open & reversible.** A missing/broken config ports everything (never silently drops an agent);
  the rename is a git-legible, lossless round-trip — flip `enabled` back and re-run.
- **Guardrails.** `check-kit.sh` verifies the active `*.md` count equals the enabled count, flags a
  disabled agent still active (apply not run), an enabled agent missing its file, and an agent file
  with no config entry; disabling a `core-phase` agent emits a warning (that phase then has no agent —
  run its `.claude/commands/<cmd>.md` runbook by hand).

When you ADD a new agent: drop `.claude/agents/<name>.md`, add a matching entry to `config/pipeline.yaml`
(else `check-kit` warns it's unmanaged), then `./setup.sh --pipeline` to regenerate the harness copies.

**What a toggle does NOT touch.** Disabling an agent parks only its `.claude/agents/<name>.md`. Its
command runbook (`.claude/commands/<cmd>.md`), any skill it used, and — for `rlm` — the
`.claude/workflows/rlm.js` engine are intentionally left in place: command files double as manual
runbooks, skills are shared, and the workflow is agent-independent. Only opencode drops a command whose
sole owner is disabled. The `.md → .md.disabled` rename is git-tracked on purpose, so your pipeline
roster is recorded in history (do **not** gitignore it); the plugin mirror excludes parked files.

## File-format conventions (match these EXACTLY)

**Subagent** — `.claude/agents/<name>.md`, YAML frontmatter + Markdown system-prompt body:
```yaml
---
name: <lowercase-hyphen>
description: >
  When to invoke this agent (drives auto-delegation). Imperative, trigger-rich.
tools: Read, Write, Edit, Bash, Grep, Glob   # allowlist; Atlassian agents add mcp__atlassian
model: sonnet | opus | haiku | inherit
skills:
  - <skill-name>
---
```
Body structure: a one-line role; **a mandatory phase + Definition-of-Done reminder**; a numbered
**Workflow**; a **Rules** list; the **handoff** update as the last step. Inline concrete tool-call
recipes — do NOT write terse "you know what to do" navigation docs (weak models need the steps spelled out).

**Skill** — `.claude/skills/<name>/SKILL.md`, minimal frontmatter:
```yaml
---
name: <name>
description: >
  Use this skill when <trigger>. ... Invoke with /<name> for the full reference.
---
```
Add `compatibility:\n  tools: [mcp__atlassian]` when the skill needs an MCP. Body: a runbook with ONE
real worked example from this repo (show-don't-tell). Optional `reference.md` sidecar for detail
(progressive disclosure). Skills must also read as standalone runbooks (open agents can't auto-load them).

**Command** — `.claude/commands/<name>.md`. Optional frontmatter (`description`, `argument-hint`,
`allowed-tools`); body is the prompt. Use `$ARGUMENTS` / `$1`. Each command must (a) state the phase,
(b) read the prior artifact, (c) write the next from the matching `templates/` file, (d) end by
restating the gate/DoD. Commands double as plain runbooks.

## Conventions every component must encode
Clean architecture (transport→service→repository, never skip); NO partial structs; English-only code;
generated code never hand-edited (sqlc/mocks/gen); branch `<type>/<TASK_ID>-<desc>`; commit
`<type>(<TASK_ID>): <desc>` (chore = version bumps only); GitFlow off `develop`; logging debug-default;
Serena symbol tools first; verify-before-claim (no hallucinated APIs); Definition of Done before "done".

## Voice
Senior, concrete, imperative. Mirror the existing repo style. Every rule carries a real example.
No stray "added for PROJ-x" comments. Most-important rules at the top and restated at the bottom.
