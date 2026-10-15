# Native harness contracts

All four adapters consume canonical `roles/*.md`, enabled integrations and the same project
inventory. `sdlc.harness.render_harness` is pure and deterministic; `sdlc.installer` owns writes.
Each adapter directory contains metadata, official references and a deterministic fixture snapshot.
Models inherit the provider session. No adapter starts workers, installs packages or connects MCP
servers during rendering.

| Harness | Project instructions and role format | Executable checked here | Native smoke |
|---|---|---|---|
| Codex | `AGENTS.md`, `.codex/config.toml`, `.codex/agents/sdlc-*.toml` | `codex-cli 0.162.1` | `codex features list` parsed generated config, exit 0 |
| Claude Code | `CLAUDE.md` imports, `.claude/settings.json`, `.claude/agents/sdlc-*.md` | `2.1.201` | `claude agents --json --settings ... --setting-sources project`, exit 0 |
| OpenCode | `opencode.json` v2 ordered permissions, `.opencode/agents/sdlc-*.md` | `v2.0.29` | version/help succeeded; `debug config` exceeded 15-second local smoke timeout |
| Cursor | `.cursor/rules/sdlc-*.mdc`, `.cursor/cli.json` | IDE launcher found; agent CLI unavailable | format snapshot only; no live IDE/agent smoke |

These checks are local configuration/probe checks. They do not prove authenticated model execution,
role selection by a model, IDE context attachment or uniform isolation. Tests explicitly distinguish
snapshots, process doubles, installed CLI parsers and missing features. Doctor runs bounded version
probes only, reports installed versions, and never turns a timeout into a supported executable.

Codex's project instructions and standalone TOML role fields were checked against the
[official AGENTS guidance](https://learn.chatgpt.com/docs/agent-configuration/agents-md),
[subagent reference](https://learn.chatgpt.com/docs/agent-configuration/subagents), and
[configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference).
Codex uses `workspace-write` with network disabled and interactive approvals; custom agents inherit
parent permissions. Project config can require trust before the provider loads it.

Claude's [subagent documentation](https://code.claude.com/docs/en/sub-agents) and
[settings documentation](https://code.claude.com/docs/en/settings) define Markdown frontmatter,
`model: inherit` and native permissions. Read-only specialists receive read/search tools. The
settings deny the listed direct secret reads and prompt for remote mutation commands; they are an additional
provider guard, not complete shell-command classification.

The [OpenCode v2 configuration](https://opencode.ai/v2/docs/config),
[agent format](https://opencode.ai/v2/docs/agents), and
[MCP reference](https://opencode.ai/v2/docs/mcp-servers) use plural `agents`, ordered permission rules,
and `mcp.servers`. Environment bindings translate to `{env:VARIABLE}`. The v1 porter remains separate;
a v1 version probe reports fallback for this v2 adapter.

Cursor's [project rules](https://prod.cursor.com/docs/rules) require `.mdc` frontmatter.
[CLI permission tokens](https://prod.cursor.com/docs/cli/reference/permissions) are generated in
project `.cursor/cli.json`; role rules provide a sequential fallback. IDE and CLI permissions differ,
and the adapter does not claim that rules isolate workers or enforce IDE approvals.

Parallel writes for every harness require the kit coordinator's separate worktrees/clones. Existing
user/global settings can change native discovery or permissions. Disabled integrations are omitted;
unknown external write capabilities require explicit authorization at the core effect boundary.
