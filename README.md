<div align="center">

# 🛠️ Open-Model SDLC Kit

**A spec-driven SDLC harness that makes a _lightweight open model_ write high-quality, convention-following Go — and runs unchanged under Claude Code.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Built for open models](https://img.shields.io/badge/built%20for-open%20models-8A2BE2)
![Works with Claude Code](https://img.shields.io/badge/works%20with-Claude%20Code-D97757)
![Agents](https://img.shields.io/badge/agents-pi%20·%20Qwen%20·%20Crush%20·%20opencode-1f6feb)
![Stack](https://img.shields.io/badge/stack-Go%20microservices-00ADD8?logo=go&logoColor=white)
![MCP](https://img.shields.io/badge/MCP-Serena%20·%20Jira%20·%20context7-111)

</div>

---

> **One canonical instruction file. A gated phase pipeline. The right MCP tools.**
> Drop the kit into a Go microservices workspace and any agent — pi, Qwen Code, Crush, opencode, or
> Claude Code — drives a ticket from **spec → clarify → plan → tasks → implement → test → review → pr**,
> producing a reviewable artifact at every gate.

Weak open models (GLM-5.1, Qwen3-Coder-Next, pi.dev-style) don't fail for lack of raw ability — they
fail at **instruction-following, planning, API hallucination, partial edits, and stopping too early**.
This kit attacks each of those directly: explicit structure, stronger tools, and hard gates the model
can't skip. The exact same files give Claude Code a phased, convention-aware workflow with zero extra
config.

<details>
<summary><b>📑 Table of contents</b></summary>

- [Why this exists](#-why-this-exists)
- [The two ideas that make it work](#-the-two-ideas-that-make-it-work)
- [The pipeline](#-the-pipeline)
- [Supported agents](#-supported-agents)
- [The tools (MCP) that lift a weak model](#-the-tools-mcp-that-lift-a-weak-model)
- [Quickstart](#-quickstart)
- [What's in the box](#-whats-in-the-box)
- [Customize for your project](#-customize-for-your-project)
- [Prerequisites](#-prerequisites)
- [Documentation](#-documentation)
- [License](#-license)

</details>

## 💡 Why this exists

| Failure mode of a weak coding model | What the kit does about it |
|---|---|
| Shallow planning, jumps straight to code | **Mandatory, announced phases** with human gates before any code |
| Hallucinated APIs / fields / proto messages | **Serena** (symbol-level reads) + **context7** (live docs) + a *verify-before-claim* rule |
| Partial edits, `// ...` elisions, zero-value structs | **No-partial-struct** + **anti-elision** rules, enforced by hooks and CI |
| Says "done" while lint/tests are red | An explicit **Definition of Done** gate: real `task lint` / `task test` must pass |
| Drifts from team conventions | One **show-don't-tell** instruction file: every rule carries a real, compilable example |

Full design rationale: **[docs/weak-model-playbook.md](docs/weak-model-playbook.md)**.

## 🧩 The two ideas that make it work

**1. One source, many harnesses.** Every durable rule lives once in [`AGENTS.md`](AGENTS.md). pi, Qwen
Code, Crush, and opencode read it natively; Claude Code reads it through a one-line `@AGENTS.md` shim in
[`CLAUDE.md`](CLAUDE.md). Per-service detail goes in a nested `AGENTS.md` (nearest file wins) — never
forked. Edit once, every agent gets it.

**2. A gated phase pipeline.** Work flows through eight phases; each writes a reviewable artifact into
`specs/<TASK_ID>-<slug>/`, the model must announce its phase, and three human gates keep it on the rails.

## 🔄 The pipeline

```mermaid
flowchart LR
    T([🎫 ticket]) --> S[1 · spec] --> C[2 · clarify] --> P[3 · plan] --> K[4 · tasks]
    K --> I[5 · implement] --> TE[6 · test] --> RV[7 · review] --> PR[8 · pr]
    classDef gate fill:#fff3cd,stroke:#d39e00,color:#5c4400,font-weight:bold;
    class C,K,RV,PR gate;
```

<sub>🟡 amber = a hard gate. **clarify** → human answers open questions · **tasks** → human approves the
list before any code · **review** → every blocker fixed · **pr** → human reviews & merges (never
self-merge).</sub>

| Phase | Command | Specialist agent | Artifact |
|---|---|---|---|
| 1 spec | `/spec` | planner | `spec.md` |
| 2 clarify | `/clarify` | planner | open questions resolved in `spec.md` |
| 3 plan | `/plan` | tech-designer | `plan.md` |
| 4 tasks | `/tasks` | tech-designer | `tasks.md` (`[P]`-parallel, AC-traceable) |
| 5 implement | `/implement` | engineer (+ devops-lead) | code, one task at a time |
| 6 test | `/test` | qa-lead | `test-plan.md` + green lint/test |
| 7 review | `/review` | go-code-reviewer | findings; spec↔plan↔tasks↔code cross-check |
| 8 pr | `/pr` | engineer | `[WIP] [TASK_ID]` PR |

Every phase also updates a legible, committed `handoff.md` so the next phase — or a fresh session —
knows exactly where the work stands. Details: **[FLOW.md](FLOW.md)**.

## 🤖 Supported agents

| Agent | Role | How it runs the pipeline |
|---|---|---|
| **Claude Code** | first-class | Reads `.claude/` subagents, commands, skills, hooks + `.mcp.json`. Zero extra config. |
| **pi** (pi.dev) | **primary open agent** | `setup.sh pi` wires MCP (`pi-mcp-adapter`), the 6 subagents (`/run`, `/chain`), read-only plan mode, and background jobs — near Claude-Code parity. |
| **Qwen Code** | secondary | Native MCP via `.qwen/settings.json`; reads `AGENTS.md`. |
| **Crush** / **opencode** | secondary | Read `AGENTS.md` + their own MCP config; commands double as plain runbooks. |

Different models can map to different roles (e.g. a stronger model for planning/review, a faster one for
implementation) — see `agents-config/pi/subagent-config.json`.

## 🔌 The tools (MCP) that lift a weak model

| Server | Why it matters for a weak model |
|---|---|
| **Serena** (semantic code over `gopls`) | Symbol-level reads/edits instead of whole files → fewer tokens, far fewer broken patches. *The* biggest win. |
| **Atlassian / Jira** (sooperset) | Reads the real ticket; (read-write default) files / updates / transitions stories. |
| **context7** | Live, version-pinned library docs → kills hallucinated / outdated APIs. |
| **sequential-thinking** | Forces explicit decomposition before coding. |
| **git**, **fetch** | Safe structured git ops; pull external specs/docs on demand. |

Core set lives in [`.mcp.json`](.mcp.json); the full menu (filesystem, postgres, playwright, github) is in
[`mcp.example.json`](mcp.example.json).

## 🚀 Quickstart

```bash
cp .env.example .env          # fill in tokens (GITHUB_PAT, JIRA_*, OPENAI_*)
./setup.sh                    # pick your agent, wire MCP, install git hooks, verify
# non-interactive: ./setup.sh pi | qwen | crush | opencode | claude
```

Then drive a ticket through the pipeline:

- **Claude Code** — `cd` into a service repo containing the kit, run `/spec PROJ-1234` … `/pr PROJ-1234`,
  or let it auto-delegate to the subagents.
- **pi** — `./setup.sh pi`, then `pi --model selfhosted/Qwen3-Coder-Next`; run `/run planner "spec PROJ-1234"`
  or `/chain` the phases. See [`agents-config/pi/README.md`](agents-config/pi/README.md).
- **Qwen Code / Crush / opencode** — start the agent in the repo; it reads `AGENTS.md` + its MCP config.

Full setup & per-agent notes: **[INSTALL.md](INSTALL.md)**.

## 📦 What's in the box

```
AGENTS.md            ← THE canonical instructions (read by pi/Qwen/Crush/opencode/Codex/Cursor)
CLAUDE.md            ← one-line @AGENTS.md shim + Claude-only extras  (single source of truth)
.mcp.json            ← core MCP set: Serena + Atlassian + context7 + sequential-thinking + git + fetch
mcp.example.json     ← full MCP menu incl. optional servers
.env.example         ← secrets template (gitignored once filled)
setup.sh             ← idempotent bootstrap (pick agent, wire MCP, verify)

agents-config/       ← per-agent adapters, all pointing at ONE OpenAI-compatible /v1 endpoint
  pi/                ← PRIMARY: models + packages + generated subagents + fallback MCP bridge
  qwen/ crush/ opencode/   ← secondary harnesses (native MCP)
  sampling-params.md ← pinned GLM-5.1 / Qwen3-Coder-Next sampling

.claude/
  agents/            ← 6 specialist subagents (planner, tech-designer, engineer, qa-lead,
                       go-code-reviewer, devops-lead)
  commands/          ← 8 phase commands (/spec /clarify /plan /tasks /implement /test /review /pr)
  skills/            ← 7 skills (serena-first, precommit, go-grpc-handler, sqlc-migration,
                       testify-suite, commit-message, jira-flow)
  rules/             ← path-scoped Go-layering rules (load only when editing internal/**)
  settings.json      ← permissions + hooks (the Claude enforcement layer)
.githooks/pre-commit ← the SAME guardrails for open agents (no hook layer) + CI

templates/           ← fill-in scaffolds: spec, plan, tasks, pr, handoff
specs/               ← per-feature artifacts: specs/<TASK_ID>-<slug>/{spec,plan,tasks,handoff}.md
docs/                ← weak-model-playbook.md (the "why") + readme-ru.md + optional-graph-engine.md
.claude-plugin/      ← plugin + marketplace manifests (optional distribution channel)
```

## 🧭 Customize for your project

The kit ships pre-filled with placeholders so the examples read like real code. Swap them for your own:

| Placeholder | Replace with | Where |
|---|---|---|
| `acme` / `Acme` | your org / display name | module paths, config, prose |
| `github.com/acme` | your private module prefix | `GOPRIVATE`, import examples |
| `PROJ`, `TEAM` | your Jira project keys | `JIRA_PROJECTS_FILTER`, examples |
| `your-org.atlassian.net` | your Atlassian site | `.env` |
| `WORKSPACE_ROOT` | your multi-repo root path | `.env` |

Project-specific rules go in a **nested `AGENTS.md`** (template: `AGENTS.nested.example.md`) — the kit's
base stays untouched and upgradeable.

## ✅ Prerequisites

`uv`/`uvx` (Serena, git/fetch MCP) · Node 18+ (`npx` servers, pi/Qwen) · Docker (Atlassian MCP) ·
Go toolchain + [`go-task`](https://taskfile.dev) · a `GITHUB_PAT` so Serena/gopls can index private
modules.

## 📚 Documentation

| Doc | What it covers |
|---|---|
| [AGENTS.md](AGENTS.md) | The canonical agent instructions (read this first) |
| [INSTALL.md](INSTALL.md) | Prerequisites, bootstrap, per-agent setup, troubleshooting |
| [FLOW.md](FLOW.md) | The eight-phase pipeline, artifacts, and state model |
| [docs/weak-model-playbook.md](docs/weak-model-playbook.md) | Why the kit is shaped this way (design rationale) |
| [docs/readme-ru.md](docs/readme-ru.md) | 🇷🇺 Русскоязычный обзор кита |
| [KIT-DEV.md](KIT-DEV.md) | Canonical facts for kit authors/maintainers |

## 📄 License

[MIT](LICENSE) © Open-Model SDLC Kit contributors.
