# QWEN.md — Open-Model SDLC Kit

> Context file for Qwen Code (and any agent) working **on this repository**. Read `AGENTS.md` first —
> it is the canonical instruction surface this kit ships to *other* agents. This file is about
> maintaining the kit itself.

## Project overview

The **Open-Model SDLC Kit** is a **spec-driven SDLC harness** — an *instruction surface*, not an
application. Its purpose is to make a lightweight **open model** (GLM-5.1, Qwen3-Coder-Next) write
high-quality, convention-following **Go** by giving it explicit structure + stronger tools + hard
gates, while running unchanged under **Claude Code**.

It drives a ticket through eight gated phases:

```
spec → clarify → plan → tasks → implement → test → review → pr
```

with three human gates (clarify, tasks, pr). Each phase reads the previous artifact and writes the
next into `specs/<TASK_ID>-<slug>/`, updating a committed `handoff.md` state file.

**The words and examples ARE the product.** This is a public template; a sloppy sentence becomes a
sloppy agent. Treat prose with the same rigor as code.

### Core design ideas

1. **One source, many harnesses.** Every durable rule lives once in `AGENTS.md`. `CLAUDE.md` is a
   one-line `@AGENTS.md` shim + a small Claude-only section. pi / Qwen / Crush / opencode read
   `AGENTS.md` natively. Per-service detail goes in a *nested* `AGENTS.md` (nearest file wins) —
   never forked. Edit once, every agent gets it.
2. **A gated phase pipeline.** Specialist subagents (planner, tech-designer, engineer, qa-lead,
   go-code-reviewer, + devops-lead specialist + rlm utility) own phases; slash commands
   (`.claude/commands/`) double as plain runbooks for agents without slash commands.
3. **Layered enforcement.** prose+examples (`AGENTS.md`) → Claude `settings.json` permissions +
   hooks → open-agent fallback in `.githooks/pre-commit` + CI. Text is context; hooks/CI are
   enforcement.

## Repository layout

| Path | What it is |
|---|---|
| `AGENTS.md` | **THE canonical instructions** (read by pi/Qwen/Crush/opencode/Codex/Cursor) |
| `CLAUDE.md` | `@AGENTS.md` shim + Claude-only extras |
| `KIT-DEV.md` | **Canonical facts for kit authors/maintainers** — read before generating kit files |
| `FLOW.md` / `INSTALL.md` / `CONTRIBUTING.md` | Pipeline, setup, and contribution docs |
| `README.md` / `docs/` | Overview + `weak-model-playbook.md` (the "why") + `readme-ru.md` (🇷🇺) |
| `.mcp.json` / `mcp.example.json` | Core MCP set (Serena, Atlassian, context7, sequential-thinking, git, fetch) + full menu |
| `setup.sh` | Idempotent bootstrap (pick agent, wire MCP, install git hooks, verify, uninstall) |
| `config/pipeline.yaml` | **Single source of truth** for which agents are active (`enabled:` toggle) |
| `config/security-policy.yaml` | Human-readable safety policy (blocked/confirm commands, secrets) |
| `scripts/` | `check-kit.sh` (verifier), `apply-pipeline.sh`, `pipeline_config.py` (YAML-subset parser) |
| `.claude/agents/` | Phase subagents (canonical source) |
| `.claude/commands/` | 8 phase commands + `/rlm` (double as runbooks) |
| `.claude/skills/` | Reusable recipes (`SKILL.md` + optional `reference.md`) |
| `.claude/hooks/` `rules/` `workflows/` `settings.json` | Claude enforcement layer + `rlm.js` engine |
| `agents-config/` | Per-agent adapters: `pi/` (primary), `qwen/`, `crush/`, `opencode/`, `sampling-params.md` |
| `templates/` | Fill-in scaffolds: spec, plan, tasks, pr, handoff |
| `specs/` | Per-feature artifacts: `specs/<TASK_ID>-<slug>/{spec,plan,tasks,handoff}.md` |
| `.githooks/pre-commit` | Open-agent guardrail fallback (no hook layer) |

## Building, running, verifying

There is no compile/build step — this is scripts + instructions. The **verifier is the test suite**.

```bash
# Verify the kit is well-formed (structure, JSON validity, frontmatter, English-only,
# pipeline-config consistency, porter syntax, workflow parse). CI runs this — it must be green.
bash scripts/check-kit.sh            # or: ./setup.sh --check
bash scripts/check-kit.sh --mcp      # also probe that Serena/Atlassian deps are runnable

# Bootstrap / configure an agent (idempotent, reversible via --uninstall)
./setup.sh                           # interactive menu
./setup.sh pi|qwen|crush|opencode|claude
./setup.sh --pipeline                # apply config/pipeline.yaml (toggle agents on/off everywhere)
./setup.sh --list-installed          # show what setup wrote (from the manifest)
./setup.sh --uninstall [agent]       # restore backups / remove created files (.env is kept)

# Regenerate derived files after editing canonical sources
python3 agents-config/pi/port-agents.py            # .claude/agents/ → agents-config/pi/agents/ (+ ~/.pi/agent/agents/)
python3 agents-config/opencode/port-to-opencode.py .opencode   # .claude/{agents,commands} → .opencode/
python3 scripts/pipeline_config.py check           # validate config/pipeline.yaml
```

**CI** (`.github/workflows/ci.yml`) runs `bash scripts/check-kit.sh` plus an internal-identifier
leak check (`git grep` for `quintegro|partfinder|thor|/home/<user>/work`) — keep the kit generic.

**Prerequisites:** `uv`/`uvx`, Node 18+, `python3`, Go toolchain + `go-task`, a `GITHUB_PAT`.
Scripts stay compatible with **macOS bash 3.2 + BSD userland** (no `grep -P`, no `mapfile`, no
GNU-only flags); Cyrillic/format checks go through `python3`. Linux or macOS only (WSL = Linux).

## Development conventions (maintaining the kit)

These are enforced by `check-kit.sh` and CI — follow them exactly.

1. **One source of truth.** Durable rules live once in `AGENTS.md`. Never duplicate a rule into
   `CLAUDE.md`. Per-service detail goes in a nested `AGENTS.md`, never forked.
2. **Stay generic — placeholders only.** This is a public template. **Never** commit a real company,
   product, service, person, host, token, or internal ticket key. Use the established placeholders:
   `acme`/`Acme` + `github.com/acme` (org / private module prefix), `PROJ`/`TEAM` (Jira keys),
   `your-org.atlassian.net` (Atlassian site), `WORKSPACE_ROOT` (multi-repo root).
3. **English only** in every shipped file (code, comments, identifiers, instructions). The single
   exception is `docs/readme-ru.md`. The verifier fails on Cyrillic anywhere else.
4. **Show, don't tell.** Every rule you add carries one real, compilable example. Weak models copy
   patterns better than they reason from abstractions. Inline concrete tool-call recipes — never
   terse "you know what to do" navigation docs.
5. **Smallest change that does the job.** No speculative abstractions or "headroom" nobody asked for.
6. **Never hand-edit generated files.** `agents-config/pi/agents/`, `.opencode/`, `opencode.json`,
   `crush.json`, `.qwen/` are **generated** (and gitignored where noted) — edit the canonical source
   in `.claude/{agents,commands}/` then regenerate with the porters. The `.md → .md.disabled` rename
   for toggled-off agents **is** git-tracked on purpose (do not gitignore it).
7. **`config/pipeline.yaml` is the only place** the agent roster is decided. `scripts/pipeline_config.py`
   is the only YAML-subset parser — the porters import it, the shell scripts shell out to it. No
   duplicated parsing (the kit's anti-drift rule). Keep the exact YAML shape (2-space `<name>:`,
   4-space attrs, inline `[a, b]` lists; no anchors/multi-line scalars).
8. **Keep the safety triad in sync:** `config/security-policy.yaml` (source of truth) ↔ the Claude
   `pre-bash` hook / `settings.json` `ask` ↔ `AGENTS.md` §8 (open-agent mirror).

### Authoring formats (match EXACTLY — see KIT-DEV.md)

- **Subagent** `.claude/agents/<name>.md`: YAML frontmatter (`name`, trigger-rich `description`,
  `tools` allowlist, `model`, `skills`) + body = one-line role, **mandatory phase + Definition-of-Done
  reminder**, numbered **Workflow**, **Rules** list, **handoff update as the last step**.
- **Skill** `.claude/skills/<name>/SKILL.md`: minimal frontmatter (`name`, `description`); body is a
  runbook with ONE real worked example from this repo; must read as a standalone runbook.
- **Command** `.claude/commands/<name>.md`: optional frontmatter; body uses `$ARGUMENTS`/`$1`; must
  (a) state the phase, (b) read the prior artifact, (c) write the next from `templates/`, (d) restate
  the gate/DoD. Doubles as a plain runbook.

### When you change…

| You change… | Then also… |
|---|---|
| A global rule/convention | edit `AGENTS.md`; re-read §0/§9 for consistency |
| A phase's behavior | edit `.claude/commands/<phase>.md`; keep it usable as a runbook |
| A specialist agent | edit `.claude/agents/<name>.md` (canonical); regenerate pi/opencode copies |
| The agent roster | edit `config/pipeline.yaml`; run `./setup.sh --pipeline` |
| A reusable recipe | edit `.claude/skills/<name>/SKILL.md`; include one worked example |
| pi wiring / packages | edit `agents-config/pi/*`; bump pinned versions as `chore(deps)` |

### Commits & PRs

- Conventional commits: `feat: …`, `fix: …`, `docs: …`, `chore(deps): …` (`chore` = version bumps only).
- PR description = an ordered list of what changed and why.
- Before opening a PR: `bash scripts/check-kit.sh` must pass; no internal identifiers; English-only;
  new rules carry a concrete example; pi/opencode subagents regenerated if `.claude/agents/` changed.

## Voice

Senior, concrete, imperative. Mirror the existing repo style. Every rule carries a real example. No
stray "added for PROJ-x" comments. Most-important rules at the top and restated at the bottom.
