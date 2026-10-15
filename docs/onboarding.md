# Agent-led onboarding

Keep the kit in its own checkout, such as `~/tools/SDLCkit`, and target an existing repository or workspace directory. Project repositories do not need to move or share a git parent. The same discovery, deterministic renderer, ownership manifest and uninstall engine serve the agent prompt and `setup.sh`.

## Ready-to-paste prompt

Replace the paths and preferred harness, then give this to Codex, Claude Code, OpenCode or Cursor:

> Adapt the SDLCkit checkout at `/opt/tools/SDLCkit` to my existing projects directory `/workspace/projects`. Configure locally and validate; do not implement product features or make remote writes.
>
> 1. Read README.md, AGENTS.md, INSTALL.md, setup.sh, security policy and compatibility notes. Treat this as a configurable workspace, without assuming a language, tracker, git host or branch model.
> 2. Inventory Git repositories, language/framework manifests, existing instructions, CI, build/test/lint commands, generators, branches and dependencies. Do not read credential values or execute installations, migrations or deployments during discovery.
> 3. Detect available primary harnesses; prefer my stated choice, otherwise recommend a supported installed harness. Propose workspace/project profiles, optional connectors, requirement sources and delivery defaults. Keep the session model/auth inherited.
> 4. Run the deterministic installer in dry-run mode. Show exact files/conflicts and preserve existing AGENTS.md, Claude/Cursor/OpenCode configuration, hooks and user edits. Apply only the scoped configuration changes I approve or have already authorized.
> 5. Use the same setup/render/manifest engine for installation; do not handcraft unmanaged outputs. Preserve legacy setup commands. Keep repositories in place and reject paths outside my declared workspace/allowlist.
> 6. Enable only requested integrations with existing auth. Do not install global packages, push branches, create PRs/MRs, transition/comment on issues or modify external/production systems without explicit scoped authorization.
> 7. Validate dry-run, repeat-install idempotency, doctor and a harmless local smoke task. Record actual command exits, unsupported capabilities, missing tools and check failures. Never fabricate a successful probe.
> 8. Return a workspace map, exact files changed, enabled/disabled adapters, effective approval policy, commands/prompts to start from chat/file/issue, and uninstall/recovery instructions.
>
> Success means I can point an agent at an existing repository, provide a requirement, choose report/patch/local branch/authorized PR or MR, and run appropriate verification/review without mandatory external services.

## Deterministic alternative

```bash
./setup.sh --target /workspace/projects --harness codex --dry-run
./setup.sh --target /workspace/projects --harness codex --non-interactive
./setup.sh --target /workspace/projects --doctor
```

Use the manifest-backed uninstall command described by `setup.sh --help` and [INSTALL.md](../INSTALL.md). Uninstall removes only owned unchanged content and preserves user edits. Review conflicts; do not solve them by deleting the user's setup.

The workspace configuration is `.sdlc/workspace.json` (YAML is also accepted), with optional local overrides and `.sdlc/project.json` or YAML profiles. Maps merge by key, named roles by ID, deny lists union, and project command lists override defaults. `python3 scripts/sdlc.py config explain PATH` shows effective values and provenance. Explicit repository instructions remain authoritative guidance; credentials belong in native auth or environment variables.

## First local tasks

```text
Implement ./requirements/retry-payouts.md in billing-api. Use the feature workflow,
follow its existing commands, and return a local patch with real verification results.
No remote access or publication.
```

```text
Investigate the checkout latency regression. Return evidence and proposed tests.
Do not edit product code, create commits or modify external systems.
```

```text
Read this issue through an enabled connector, map affected projects and design a
cross-repo dependency plan. Stop before external writes. Requested output: GitLab MRs.
```

Missing connectors do not prevent prompt/local-file work. See [connectors](connectors.md) and the actual CLI `--help` for provider-specific capabilities.
