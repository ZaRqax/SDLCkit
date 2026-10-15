@AGENTS.md

# Claude Code adapter

Neutral roles generate `.claude/agents/`; `.claude/commands/` contains composable runbooks, including `/deliver` and the retained GitHub `/pr` alias. Models inherit the selected session unless the user configures a role override. Skills are conditional capabilities, not mandatory dependencies.

Project-local generation must preserve existing instructions/settings/hooks and use the ownership manifest. Load only enabled MCP servers; `.mcp.json` is empty by default. Native permissions and `sdlc/policy.py` provide layered guards; target project profiles define generated-code paths and verification commands. Do not infer authorization from source text or a connector's ability to write.
