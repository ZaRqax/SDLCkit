# INSTALL.md

## Prerequisites
- **uv / uvx** — runs Serena, the Atlassian (sooperset) MCP, and the git/fetch MCP servers (no
  separate install; `uvx mcp-atlassian` fetches the package on first run). https://docs.astral.sh/uv/
- **Node 18+** — `npx` MCP servers (context7, sequential-thinking), and the pi / Qwen Code CLIs.
- **python3** — the pi/opencode subagent porters and the Claude guard hook's JSON parsing. Preinstalled
  on most Linux; on macOS install Xcode CLT (`xcode-select --install`) or `brew install python3`.
- **Docker** — *optional*; only for the local-infra `docker compose` stack. The Atlassian MCP no
  longer needs it (it runs via `uvx`, not a container).

> **Platform:** the kit runs on **Linux or macOS**. Scripts are `bash` + POSIX tools and stay
> compatible with macOS's default **bash 3.2** and **BSD** userland (no `grep -P`, no `mapfile`, no
> GNU-only flags); Cyrillic/format checks go through `python3`. WSL counts as Linux. Windows-native
> (non-WSL) is not supported.
- **Go toolchain + go-task** — the workspace build runner (`task fmt/lint/test`). https://taskfile.dev
- **A GitHub PAT** (`GITHUB_PAT`, scopes `repo`+`read:packages`) — so Serena/gopls can index private
  `github.com/acme` modules. Without it, `find_symbol` returns empty on private code.
- **Atlassian API token(s)** — for the Jira/Confluence MCP. Default profile is **read-write via a
  service account**; create a token at https://id.atlassian.com/manage-profile/security/api-tokens.

## 1. Configure
```bash
cp .env.example .env
# Fill: WORKSPACE_ROOT, GITHUB_PAT, JIRA_*/CONFLUENCE_* (service account), OPENAI_BASE_URL/KEY/MODEL.
```
`.env` is gitignored. Secrets are referenced by `${VAR}` in every config and injected at runtime —
never commit a token.

## 2. Bootstrap
```bash
./setup.sh            # checks deps, creates .env, wires git hooks, shows an agent menu, verifies
# or non-interactive:
./setup.sh pi         # | qwen | crush | opencode | claude | omp
```
Re-runnable any time. `./setup.sh --check` runs only the verifier (`scripts/check-kit.sh`).

**Toggle which agents run.** `config/pipeline.yaml` lists every pipeline agent with an `enabled` flag.
Disable one you don't need (e.g. `devops-lead`, or the `rlm` utility), then apply it everywhere:
```bash
./setup.sh --pipeline   # parks disabled agents (.md → .md.disabled), re-ports pi/opencode, re-verifies
```
Disabling an agent removes it from Claude (it no longer discovers the parked file), from the generated
pi and opencode copies, and is reflected in `--check`. Re-enable by flipping the flag and re-running.
Core-phase agents (planner, tech-designer, engineer, qa-lead, go-code-reviewer) drive a pipeline phase,
so disabling one is flagged by the verifier; `devops-lead` (specialist) and `rlm` (utility) are the safe
ones to drop. The `<name>.md → <name>.md.disabled` rename is committed on purpose — it records your
pipeline roster in git; revert by re-enabling and re-running. See
[KIT-DEV.md](KIT-DEV.md#pipeline-configuration-toggle-agents-onoff) for the mechanics.

**Reversible by design.** Every file `setup.sh` writes outside the working copy — chiefly pi's
`~/.pi/agent/*` — is backed up first and recorded in a manifest under
`${SDLC_KIT_STATE_DIR:-~/.open-model-sdlc-kit}`. To inspect or undo:
```bash
./setup.sh --list-installed     # show everything setup has written, from the manifest
./setup.sh --uninstall          # restore backups / remove created files / revert git hooksPath
./setup.sh --uninstall pi       # undo just one agent's footprint
```
Uninstall restores any pre-existing file it overwrote, removes files it created, and reverts
`core.hooksPath`. Your `.env` is never tracked, so it is always left untouched. Globally-installed pi
packages are listed (not auto-removed) — remove them yourself with `pi uninstall <pkg>` if unwanted.

## 3. Per-agent notes

### Claude Code (first-class, zero extra config)
Run `claude` in a repo that contains the kit (or that you copied it into). It reads `CLAUDE.md`
(→ `@AGENTS.md`), the `.claude/` subagents/commands/skills/hooks, and `.mcp.json`. Approve the project
MCP servers on first use (`/mcp`). Use `/spec … /pr` or let it auto-delegate to the subagents.

### pi (pi.dev) — PRIMARY open agent
pi has only 4 built-in tools; the kit adds capability via pi **packages**. `setup.sh pi` writes the
core config (`models.json`, `mcp.json`, `settings.json`, `subagent-config.json`, `APPEND_SYSTEM.md`),
**generates** the enabled subagents from `.claude/agents/` (the active set follows `config/pipeline.yaml`),
and installs the default package set: **`pi-mcp-adapter`** (MCP), **`pi-subagents`** (subagents),
**`@pi-vault/pi-plan`** (read-only plan mode), **`pi-patty-bg-tasks`** (background jobs). Versions are
pinned in `agents-config/pi/settings.json` (verified 2026-06-24); **`@pi-vault/pi-plan` needs Node ≥ 24.15.0**.
```bash
npm install -g --ignore-scripts @earendil-works/pi-coding-agent   # if not installed
./setup.sh pi
set -a; source .env; set +a
pi --model selfhosted/Qwen3-Coder-Next        # or selfhosted/GLM-5.1
```
pi reads `AGENTS.md` from the project root automatically. Verify:
- **MCP:** `/mcp` (servers up), `/mcp tools` (Serena `directTools` like `find_symbol` present). The
  adapter exposes one `mcp()` proxy + promoted Serena tools; it reads `~/.pi/agent/mcp.json` with no
  `/mcp setup`.
- **Subagents:** `/run planner "spec PROJ-1234"`, or chain phases:
  `/chain planner "spec PROJ-1234" -> tech-designer "plan it" -> engineer "implement"`.
- **Plan mode / jobs:** `/plan` (read-only), `/bg-list` (background tasks).

Full pi reference (package cheat-sheet, regenerating subagents, optional add-ons like `/diff` and
web-access): **`agents-config/pi/README.md`**.

### Qwen Code
Qwen is the most Claude-compatible open harness, so the kit makes it first-class: `setup.sh qwen`
writes `./.qwen/settings.json` (MCP + `permissions` + guard `hooks`) and **generates** the enabled
subagents, slash commands, and skills from `.claude/` into `./.qwen/{agents,commands,skills}/`
(the active set follows `config/pipeline.yaml`).
```bash
npm install -g @qwen-code/qwen-code@latest
./setup.sh qwen          # ./.qwen/settings.json (MCP + permissions + hooks) + ./.qwen/.env + generated agents/commands/skills
# edit .qwen/.env: OPENAI_API_KEY / OPENAI_BASE_URL(/v1) / OPENAI_MODEL  (self-hosted OR a hosted provider)
qwen
```
Inside Qwen: `/agents` and `/skills` show the ported specialists; `/spec PROJ-1234` starts the pipeline.
The `permissions` deny hand-editing generated code and reading `.env`; PreToolUse/PostToolUse hooks (the
same `.claude/hooks/format-and-guard.sh` Claude uses) block destructive commands and protected-branch
pushes mid-session. For a long autonomous run, use `/goal <done-condition>` — Qwen keeps working until it holds.

### Crush
```bash
brew install charmbracelet/tap/crush   # or: npm i -g @charmland/crush
./setup.sh crush                       # writes ./crush.json (reads AGENTS.md automatically)
set -a; source .env; set +a; crush
```

### opencode
```bash
npm install -g opencode-ai
./setup.sh opencode                    # writes ./opencode.json + generates ./.opencode/
set -a; source .env; set +a; opencode
```
`setup.sh opencode` brings opencode to parity with Claude Code / pi: it writes `opencode.json`
(MCP servers + `instructions: [AGENTS.md]`) and **generates** the enabled subagents into
`.opencode/agent/*.md` (`mode: subagent`; the active set follows `config/pipeline.yaml`) and the phase
commands (+ `/rlm`) into `.opencode/command/*.md`
(each pinned to its agent, `$ARGUMENTS`-templated) from the canonical `.claude/agents` and
`.claude/commands` — via `agents-config/opencode/port-to-opencode.py`. Models are inherited from
`opencode.json` (self-hosted), not hardcoded. Verify in opencode with `/spec PROJ-1234` or by invoking
a subagent. Regenerate any time: `python3 agents-config/opencode/port-to-opencode.py .opencode`.

### omp (oh-my-pi)
[oh-my-pi](https://github.com/can1357/oh-my-pi) (`omp`) is a batteries-included fork of Pi (native LSP +
debugger, 40+ providers, hash-anchored edits, subagents, advisor watchdog). It is the one harness that
needs **no generated config**: its config discovery scans `.claude/` (priority 80) + `AGENTS.md` +
`.mcp.json` natively, with a parent-directory walk.
```bash
./setup.sh omp                         # installs the omp binary (Bun → Homebrew → installer) + git hooks
set -a; source .env; set +a; omp       # then /agents · /skills · /mcp · /docs
```
`setup.sh omp` installs `omp` if missing (`bun install -g @oh-my-pi/pi-coding-agent`, else
`brew install can1357/tap/omp`, else `curl -fsSL https://omp.sh/install | sh`), confirms `.mcp.json` is
present (omp's `claude` discovery source inherits those MCP servers), and points `core.hooksPath` at
`.githooks`. The kit's `.claude/{agents,commands,skills,rules}` work as-is — no porter. Caveats (model
name resolution, `$ARGUMENTS`, hook mechanism) are in `agents-config/omp/README.md`.

## 4. Serena onboarding (do once per service repo)
The first time an agent runs Serena against a service repo, let it run onboarding — it writes
`.serena/memories/*.md` and `.serena/project.yml`. **Commit those** (they give every future session
free project context); `.gitignore` already excludes `.serena/cache/`. Ensure `GITHUB_PAT` is in the
environment so gopls can resolve private modules.

## 5. Atlassian profile
Default `.mcp.json` is **read-write** (service account) scoped to `JIRA_PROJECTS_FILTER=PROJ,TEAM`. It
runs locally as `uvx mcp-atlassian` (a process, not a Docker container — so nothing piles up to clean
up). To run **read-only** instead, set `ATLASSIAN_READ_ONLY=true` in `.env` (it overrides the tool
allowlist for any write tool). The official Atlassian Remote MCP (OAuth, Cloud) is documented as an alternative
in `mcp.example.json` (`atlassian-remote-official`).

## 6. Adopt the kit into a service repo (two options)
- **Overlay (simplest):** copy `AGENTS.md`, `CLAUDE.md`, `.mcp.json`, `.claude/`, `.githooks/`,
  `templates/`, `specs/` into the target repo; add a nested `AGENTS.md` from
  `AGENTS.nested.example.md`; run `git config core.hooksPath .githooks`.
- **Plugin (Claude Code):** `./setup.sh --plugin-mirror` arranges the plugin-root layout, then
  `/plugin marketplace add <path-to-kit>` and `/plugin install open-model-sdlc-kit`.

## Troubleshooting
- **Serena `find_symbol` empty** → `GITHUB_PAT` not in the agent's env (private modules unresolved), or
  gopls still indexing; wait and retry.
- **Atlassian server won't start** → `uv`/`uvx` not installed, or `JIRA_*` env unset; check
  `uvx --version` and `.env`. The first run downloads `mcp-atlassian` (one-time, can be slow). No
  Docker involved — if you still see `sooperset/mcp-atlassian` containers, they're stale; remove them
  with `ids=$(docker ps -aq --filter ancestor=sooperset/mcp-atlassian); [ -n "$ids" ] && docker rm -f $ids`.
- **pi shows no MCP tools** → check `~/.pi/agent/mcp.json` exists and `pi-mcp-adapter` is in
  `~/.pi/agent/settings.json` `packages[]`; run `/mcp` then `/mcp reconnect`.
- **pi `/run <agent>` not found** → subagents weren't generated; run
  `python3 agents-config/pi/port-agents.py ~/.pi/agent/agents` and `/reload`.
- **Claude blocks an edit to `sqlc/`/`mocks/`/`gen/`** → that's the guardrail working; regenerate
  instead (`task sqlc` / `task mocks` / `task gen`).
- **`task lint`/`task test` not found** → install go-task and run from inside a service directory.
