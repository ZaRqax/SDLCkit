# INSTALL.md

## Prerequisites
- **uv / uvx** — runs Serena and the git/fetch MCP servers (no separate install). https://docs.astral.sh/uv/
- **Node 18+** — `npx` MCP servers (context7, sequential-thinking), and the pi / Qwen Code CLIs.
- **Docker** — runs the Atlassian (sooperset) MCP server.
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
./setup.sh            # checks deps, creates .env, wires git hooks, prompts for your agent, verifies
# or non-interactive:
./setup.sh pi         # | qwen | crush | opencode | claude
```
Re-runnable any time. `./setup.sh --check` runs only the verifier (`scripts/check-kit.sh`).

## 3. Per-agent notes

### Claude Code (first-class, zero extra config)
Run `claude` in a repo that contains the kit (or that you copied it into). It reads `CLAUDE.md`
(→ `@AGENTS.md`), the `.claude/` subagents/commands/skills/hooks, and `.mcp.json`. Approve the project
MCP servers on first use (`/mcp`). Use `/spec … /pr` or let it auto-delegate to the subagents.

### pi (pi.dev) — PRIMARY open agent
pi has only 4 built-in tools; the kit adds capability via pi **packages**. `setup.sh pi` writes the
core config (`models.json`, `mcp.json`, `settings.json`, `subagent-config.json`, `APPEND_SYSTEM.md`),
**generates** the 6 subagents from `.claude/agents/`, stages the fallback MCP bridge (disabled), and
installs the default package set: **`pi-mcp-adapter`** (MCP), **`pi-subagents`** (subagents),
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

Full pi reference (package cheat-sheet, the adapter↔fallback toggle, regenerating subagents, optional
add-ons like `/diff` and web-access): **`agents-config/pi/README.md`**.

### Qwen Code
```bash
npm install -g @qwen-code/qwen-code@latest
./setup.sh qwen          # writes ./.qwen/settings.json (MCP) + ./.qwen/.env
# edit .qwen/.env: OPENAI_API_KEY / OPENAI_BASE_URL(/v1) / OPENAI_MODEL
qwen
```

### Crush
```bash
brew install charmbracelet/tap/crush   # or: npm i -g @charmland/crush
./setup.sh crush                       # writes ./crush.json (reads AGENTS.md automatically)
set -a; source .env; set +a; crush
```

### opencode
```bash
npm install -g opencode-ai
./setup.sh opencode                    # writes ./opencode.json (instructions: [AGENTS.md])
set -a; source .env; set +a; opencode
```

## 4. Serena onboarding (do once per service repo)
The first time an agent runs Serena against a service repo, let it run onboarding — it writes
`.serena/memories/*.md` and `.serena/project.yml`. **Commit those** (they give every future session
free project context); `.gitignore` already excludes `.serena/cache/`. Ensure `GITHUB_PAT` is in the
environment so gopls can resolve private modules.

## 5. Atlassian profile
Default `.mcp.json` is **read-write** (service account) scoped to `JIRA_PROJECTS_FILTER=PROJ,TEAM`. To
run **read-only** instead, set `ATLASSIAN_READ_ONLY=true` in `.env` (it overrides the tool allowlist
for any write tool). The official Atlassian Remote MCP (OAuth, Cloud) is documented as an alternative
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
- **Atlassian server won't start** → Docker not running, or `JIRA_*` env unset; check `docker ps` and
  `.env`. Tokens are passed by name (`-e JIRA_API_TOKEN`), so they must be exported.
- **pi shows no MCP tools** → check `~/.pi/agent/mcp.json` exists and `pi-mcp-adapter` is in
  `~/.pi/agent/settings.json` `packages[]`; run `/mcp` then `/mcp reconnect`. (Offline fallback: enable
  the bundled `mcp-bridge` — see `agents-config/pi/mcp-extension/README.md`; never run both.)
- **pi `/run <agent>` not found** → subagents weren't generated; run
  `python3 agents-config/pi/port-agents.py ~/.pi/agent/agents` and `/reload`.
- **Claude blocks an edit to `sqlc/`/`mocks/`/`gen/`** → that's the guardrail working; regenerate
  instead (`task sqlc` / `task mocks` / `task gen`).
- **`task lint`/`task test` not found** → install go-task and run from inside a service directory.
