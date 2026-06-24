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
  Qwen Code (native MCP), Crush, opencode.
- **pi package set (default):** `pi-mcp-adapter` (MCP — replaces the hand-rolled bridge, which is kept
  only as a documented offline fallback in `agents-config/pi/mcp-extension/`), `pi-subagents`
  (subagents — generated from `.claude/agents/` by `agents-config/pi/port-agents.py` into
  `~/.pi/agent/agents/`; `agents-config/pi/agents/*.md` is GENERATED, don't hand-edit), `@pi-vault/pi-plan`
  (read-only plan-mode guardrail), `pi-patty-bg-tasks` (background test/lint jobs). The adapter reads
  the same `agents-config/pi/mcp.json` as the fallback (`directTools` promote hot Serena tools; `lazy`
  lifecycle elsewhere). Optional/off by default: `@geminixiang/pi-diff`, `pi-web-access`,
  `rpiv-ask-user-question`, `pi-permission-system`, `pi-hypa`. Rejected: `pi-lens` (overlaps Serena +
  gofumpt), memory packages (overlap `.serena/memories`), `rpiv-todo` (overlaps `tasks.md`). Versions pinned & verified vs the npm registry 2026-06-24
(adapter 2.10.0, subagents 0.31.0, pi-plan 0.1.0, bg-tasks 0.2.0, pi CLI 0.80.2); `@pi-vault/pi-plan`
needs Node ≥24.15.0.
- **Co-primary models = GLM-5.1 + Qwen3-Coder-Next**, served over an OpenAI-compatible `/v1` endpoint.
  Sampling pinned in `agents-config/sampling-params.md`.
- **Code intelligence = Serena** (uvx-from-git, over gopls). Mandated over whole-file reads/edits.
  Commit `.serena/memories` + `.serena/project.yml`; gitignore `.serena/cache`. Needs `GITHUB_PAT`
  so gopls can index private `github.com/acme` modules.
- **Jira/Confluence = sooperset/mcp-atlassian (Docker).** Default profile is **READ-WRITE via a
  service account**, scoped to `JIRA_PROJECTS_FILTER=PROJ,TEAM`. A read-only profile is one env var away
  (`ATLASSIAN_READ_ONLY=true`). Official Atlassian Remote MCP documented as the Cloud/OAuth alternative.
- **Core MCP set** (`.mcp.json`): serena, atlassian, context7, sequential-thinking, git, fetch.
  **Optional** (in `mcp.example.json`): filesystem (core for open agents), postgres-mcp-pro (restricted),
  playwright (UI repos), official github. **Banned:** `@modelcontextprotocol/server-postgres` (CVE) and
  `@modelcontextprotocol/server-github` (archived).
- **Enforcement is layered:** prose+examples (AGENTS.md) → Claude `settings.json` permissions + hooks →
  open-agent fallback in `.githooks/pre-commit` + CI. Text is context; hooks/CI are enforcement.
- **Optional, NOT core:** the heavy spec↔code graph/drift engine (documented in `docs/optional-graph-engine.md`).

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
