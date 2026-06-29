# FLOW.md — the SDLC pipeline

The kit runs work through eight gated phases. Each phase reads the previous artifact and writes the
next into `specs/<TASK_ID>-<slug>/`, and updates the legible state file `handoff.md`. Three human
gates keep a weak model on the rails: **approve the clarified spec**, **approve the task list**,
**review the PR**.

```
  Jira ticket
      │
 ┌────▼─────┐   /spec        planner          spec.md
 │ 1 SPEC   │────────────────────────────────────────────────►
 └────┬─────┘
 ┌────▼─────┐   /clarify     planner          spec.md §6 resolved
 │ 2 CLARIFY│  ◆ GATE: human answers open questions
 └────┬─────┘
 ┌────▼─────┐   /plan        tech-designer    plan.md
 │ 3 PLAN   │────────────────────────────────────────────────►
 └────┬─────┘
 ┌────▼─────┐   /tasks       tech-designer    tasks.md  ([P], AC-traceable, story files)
 │ 4 TASKS  │  ◆ GATE: human approves tasks.md before any code
 └────┬─────┘
 ┌────▼─────┐   /implement   engineer         code (one task at a time, Serena symbol edits)
 │ 5 IMPL   │────────────────────────────────────────────────►
 └────┬─────┘
 ┌────▼─────┐   /test        qa-lead          test-plan.md + green task lint/test  ◆ Definition of Done
 │ 6 TEST   │────────────────────────────────────────────────►
 └────┬─────┘
 ┌────▼─────┐   /review      go-code-reviewer findings; spec↔plan↔tasks↔code cross-check
 │ 7 REVIEW │  ◆ every blocker fixed (bounce → engineer)
 └────┬─────┘
 ┌────▼─────┐   /pr          engineer         [WIP] [TASK_ID] PR (templates/pr-template.md)
 │ 8 PR     │  ◆ GATE: human reviews & merges (≥2 approvals; never self-merge)
 └──────────┘
```

## Artifacts per feature (`specs/<TASK_ID>-<slug>/`)
| File | Written in | From template |
|---|---|---|
| `spec.md` | spec + clarify | `templates/spec-template.md` |
| `plan.md` | plan | `templates/plan-template.md` |
| `tasks.md` | tasks | `templates/tasks-template.md` |
| `test-plan.md` | test | (inline format in qa-lead) |
| `handoff.md` | every phase | `templates/handoff-template.md` |

## State & resumption
`handoff.md` is the committed, legible source of truth: Status, Phase, Next agent, a pipeline
checklist, quality gates, decisions, blockers, and an append-only Log. Any agent (or a fresh session)
reads it to know exactly where the work stands and who runs next. `specs/INDEX.md` rolls feature
statuses up across the workspace. (An optional JSON mirror `handoff/<TASK_ID>.json` exists only for
the optional automation/graph layer — see `docs/optional-graph-engine.md`.)

## Running it
- **Claude Code:** invoke the slash commands `/spec … /pr`, or let it auto-delegate to the subagents
  in `.claude/agents/` by description.
- **pi / Qwen Code / Crush / opencode:** the same command files in `.claude/commands/` read as plain
  runbooks — paste or reference them; the AGENTS.md workflow (§2) drives the same phases.
- **omp (oh-my-pi):** reads `.claude/commands/` as native slash commands and `.claude/agents/` as
  subagents directly (plus `AGENTS.md` + `.mcp.json`) — like Claude, no generated copies.
- **Bug flow:** a bug still gets a spec (type: fix). For a tracked bug, planner files/links a Jira Bug
  via the `jira-flow` skill before the fix is written.

## Configuring which agents run
The roster is data, not hard-wired: `config/pipeline.yaml` lists each agent with an `enabled` flag.
Disable the ones you don't use (e.g. `devops-lead` if you have no infra work, or the `rlm` utility) and
run `./setup.sh --pipeline` — it removes them from every harness and re-verifies. The five core-phase
agents (planner, tech-designer, engineer, qa-lead, go-code-reviewer) each own a phase above, so keep
them on unless you intend to run that phase's command by hand. Mechanics: KIT-DEV.md.
