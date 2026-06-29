# Contributing

Thanks for improving the **Open-Model SDLC Kit**. This kit is an *instruction surface* for coding
agents, so the bar is a little different from a normal codebase: the words and examples **are** the
product. A sloppy sentence becomes a sloppy agent.

## Ground rules

1. **One source of truth.** Durable rules live once in [`AGENTS.md`](AGENTS.md). `CLAUDE.md` is only a
   `@AGENTS.md` shim plus a small Claude-only section. Don't duplicate a rule into both — edit `AGENTS.md`.
2. **Stay generic.** This is a public template. **Never** commit a real company, product, service,
   person, host, token, or internal ticket key. Use the established placeholders:
   | Placeholder | Means |
   |---|---|
   | `acme` / `Acme`, `github.com/acme` | your org / private module prefix |
   | `PROJ`, `TEAM` | Jira project keys |
   | `your-org.atlassian.net` | Atlassian site |
   | `WORKSPACE_ROOT` | multi-repo root path |
3. **English only** in every shipped file (code, comments, identifiers, instructions). The single
   exception is `docs/readme-ru.md`. The CI verifier fails on Cyrillic anywhere else.
4. **Show, don't tell.** Every rule you add should carry one real, compilable example. Weak models copy
   patterns better than they reason from abstractions — see [docs/weak-model-playbook.md](docs/weak-model-playbook.md).
5. **Smallest change that does the job.** No speculative abstractions or "headroom" nobody asked for.

## How the pieces fit

| You want to change… | Edit… | Then… |
|---|---|---|
| A global rule/convention | `AGENTS.md` | re-read §0/§9 to keep it consistent |
| A phase's behavior | `.claude/commands/<phase>.md` | keep it usable as a plain runbook too |
| A specialist agent | `.claude/agents/<name>.md` (canonical) | regenerate pi subagents (below) |
| A reusable recipe | `.claude/skills/<name>/SKILL.md` | include one worked example |
| A scaffold | `templates/*.md` | keep fill-in markers obvious |
| pi wiring / packages | `agents-config/pi/*` | bump pinned versions as `chore(deps)` |

**The pi subagents under `agents-config/pi/agents/` are generated** — don't hand-edit them. Edit the
canonical agents in `.claude/agents/`, then:

```bash
python3 agents-config/pi/port-agents.py        # regenerate agents-config/pi/agents/
```

Authoring formats (frontmatter, body structure) are specified in [KIT-DEV.md](KIT-DEV.md).

## Before you open a PR

```bash
bash scripts/check-kit.sh        # structure, JSON validity, frontmatter, English-only, pi setup
```

CI runs the same verifier on every push and pull request — it must be green.

Quick self-check:

- [ ] No internal identifiers introduced (placeholders only).
- [ ] English-only in shipped files (RU doc excepted).
- [ ] New rules carry a concrete example.
- [ ] pi subagents regenerated if `.claude/agents/` changed.
- [ ] `scripts/check-kit.sh` passes.

## Commits & PRs

- Conventional commits: `feat: …`, `fix: …`, `docs: …`, `chore(deps): …`.
- Keep the PR description to an ordered list of what changed and why.
- Be kind in review; the goal is a kit that makes *every* agent better.
