# `agents-config/omp/` — oh-my-pi (omp)

[oh-my-pi](https://github.com/can1357/oh-my-pi) (`omp`) is a batteries-included **fork of
[Pi](https://github.com/badlogic/pi-mono)** by @can1357: a terminal coding agent with the IDE wired in
— native LSP (14 ops) and debugger/DAP (28 ops), 40+ providers, 32 built-in tools, hash-anchored edits,
first-class subagents (`task`), an advisor watchdog, time-traveling stream rules, and native git/web
tools. Binary: **`omp`**.

## Why there is NO porter for omp

Unlike Qwen/opencode (which need `.claude/` regenerated into their own format), **omp reads the kit's
existing files natively**. Its config discovery scans four source roots in priority order —
`.omp` (100) > **`.claude` (80)** > `.codex` (70) > `.gemini` (60) — at both user level
(`~/.omp/agent`, `~/.claude`) and project level (`<cwd>/.omp`, `<cwd>/.claude`), and it **walks parent
directories** (monorepo/workspace friendly). The `claude` source is enabled by default and contributes
context files, **MCP servers**, commands, skills, hooks, tools, prompts, and settings.

So with the kit already laid down, omp picks up — **with zero generated copies**:

| Kit file | Read by omp as | Via |
|---|---|---|
| `AGENTS.md` | canonical instructions | top-level `AGENTS.md` (native + claude) |
| `.claude/agents/*.md` | phase subagents | `claude` source, `agents/` |
| `.claude/commands/*.md` | slash commands `/spec … /pr` | `claude` source, `commands/` |
| `.claude/skills/*/SKILL.md` | skills (same `SKILL.md` format) | `claude` source, `skills/` (ancestor scan) |
| `.claude/rules/*.md` | rules | `claude` source, `rules/` |
| `.mcp.json` | MCP servers (Serena, Atlassian, context7, …) | `claude` source contributes MCP |

**Do not** set `disabledProviders: [claude]` in omp settings — that would turn off exactly the
inheritance above.

## Install

`setup.sh omp` installs the binary if missing (it checks `command -v omp` first), preferring Bun:

```bash
bun install -g @oh-my-pi/pi-coding-agent     # recommended (requires bun ≥ 1.3.14)
brew install can1357/tap/omp                 # Homebrew
curl -fsSL https://omp.sh/install | sh       # installer script
mise use -g github:can1357/oh-my-pi           # pinned via mise
```

## What `setup.sh omp` does

1. Installs/verifies the `omp` binary (Bun → Homebrew → installer script).
2. Confirms `.mcp.json` is present (the kit ships it) — omp's `claude` source inherits those MCP
   servers. `${VAR}` in `.mcp.json` is interpolated from the environment, so `source .env` first.
3. Points `core.hooksPath` at `.githooks` (the commit-time guardrail is harness-independent).
4. Verifies (`omp --version`).

```bash
source .env          # export GITHUB_PAT / JIRA_* / etc. so .mcp.json ${VAR} resolves
./setup.sh omp
omp                  # then inside: /agents · /skills · /mcp · /docs
```

## omp-native features that complement the kit

These are extras omp gives you on top of the pipeline; nothing to configure for the basics:

- **Native LSP** — `rename`/`references`/diagnostics through the language server. For Go symbol work
  this can stand in for Serena; the kit's `AGENTS.md §6` Serena recipe still works via MCP if you prefer.
- **Subagents (`task`)** — typed, schema-validated fan-out into isolated worktrees; pairs naturally with
  the kit's phase agents and the `rlm` decompose-and-merge skill.
- **Stream rules + advisor watchdog** — a regex can abort a stray stream mid-token and inject a rule;
  an optional reviewer model watches every turn. This is omp's mid-session enforcement analogue to the
  Claude `pre-bash`/`pre-edit` hooks. The commit-time `.githooks/pre-commit` guard still applies regardless.
- **`/review`** — P0–P3 ranked review with a ship/no-ship verdict; a good companion to the kit's
  `go-code-reviewer` phase.
- **Hindsight memory** — project-scoped `retain`/`recall` across sessions.

## Caveats

- **Agent `model:`** — the kit's agents say `model: opus`/`sonnet`/`inherit`. omp resolves these against
  its own 40-provider catalog; if a name doesn't resolve, set a concrete model (`omp --model <id>`) or
  adjust the agent's `model:` for omp.
- **Command args** — omp interpolates `$ARGUMENTS`; the kit's commands also use `$1`, which omp may leave
  literal. If a command echoes `$1`, invoke it with the argument and rely on `$ARGUMENTS`.
- **Hooks** — omp's hook subsystem loads `hooks/pre|post/*` modules (Bun import), not Claude's
  `settings.json` command hooks. The kit's shell guard therefore runs at **commit time** (`.githooks`)
  for omp; mid-session, rely on omp's permission prompts + stream rules + advisor.
- **MCP env** — `source .env` before launching so `${GITHUB_PAT}` etc. in `.mcp.json` resolve.

## Optional: an omp-native `.omp/`

You only need `.omp/` if you want omp-specific overrides (higher priority than `.claude/`): e.g.
`.omp/rules/*.md` stream rules, `.omp/skills/*/SKILL.md`, or `.omp/config.yml` settings
(`~/.omp/agent/config.yml` is the global layer). The kit does not generate one — `.claude/` inheritance
covers the pipeline. `/.omp/` is gitignored.
