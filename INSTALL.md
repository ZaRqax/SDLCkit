# Install SDLCkit in an existing workspace

SDLCkit can live anywhere outside your repositories. Projects stay in their current directories.
Python 3.10+, Git and Bash are required for the local kit. Linux, macOS and WSL are supported;
native Windows is not yet supported. Install your preferred coding agent separately. Go, Node,
Docker, Taskfile, MCP servers and tracker accounts are needed only when your projects use them.
No package installation or background service starts during scoped setup.

## Agent-led onboarding

Open the kit in Codex, Claude Code, OpenCode or Cursor and provide:

```text
Adapt this SDLCkit checkout to my existing projects at /absolute/path/to/projects.
Inspect README.md, AGENTS.md, INSTALL.md and config/security-policy.yaml.
Discover repositories, stacks, commands and existing instructions without reading secrets
or running project code. Use scripts/discover-workspace.py and scripts/render-harness.py.
Select an installed harness; show the exact dry-run diff and ownership conflicts first.
Preserve existing rules, hooks and provider config. Configure locally and validate; no
package installs, remote writes, migrations, deployments or background watchers.
Finish with the workspace map, generated files, enabled capabilities, verification evidence,
a prompt to start work, and rollback/uninstall instructions.
```

Agents and shell users use the same discovery, renderer, manifest and recovery engine.

## Deterministic script setup

```bash
./setup.sh --target '/absolute/path/projects' --harness all --dry-run
./setup.sh --target '/absolute/path/projects' --harness codex --profile auto --non-interactive
./setup.sh --doctor --target '/absolute/path/projects'
./setup.sh --target '/absolute/path/projects' --list-installed
./setup.sh --target '/absolute/path/projects' --uninstall
```

Choose `codex`, `claude`, `opencode`, `cursor`, `all` or `auto`. `auto` honors the configured
preferred harness, then probes installed CLIs. An explicitly selected provider may be rendered
before its executable is installed; doctor reports availability honestly. OpenCode's new adapter
targets v2; the legacy porter remains available for v1. Models inherit the selected provider.
`--profile auto` detects a Go-only repository and applies the optional Go profile; `generic` has
no stack assumptions. Discovery commands are suggestions until their definitions are inspected.
`--config path/to/workspace.yaml` selects explicit versioned configuration.

The CLI prints JSON containing the inventory, effective configuration, conflicts and unified diffs.
Exit `0` means the requested operation completed or previewed; `1` means an error/conflict;
argument errors return `2`. `--help` lists the exact supported flags. `--non-interactive` never
prompts and has the same conservative conflict policy. Dry-run performs no writes, including
state, backups, locks or Python bytecode; run the provided entry points with `python3 -B` when
calling them directly.

Existing files remain user-owned. An existing `AGENTS.md` causes an explicit conflict. After
reviewing its scoped addition, `--merge` authorizes an appended, marked Markdown block; existing
JSON/TOML/provider settings require explicit manual reconciliation and are never silently merged.
Preview omits user configuration bodies to avoid printing credentials. No target setup changes
`$HOME`, global CLI settings, existing Git hooks or `core.hooksPath`.

## Ownership and recovery

Generated files are tracked under the selected target's `.sdlc/generated-manifest.json`, with
original content, ownership per harness and SHA-256 hashes. Each repository receives scoped
instructions, provider assets, `.sdlc/project.json` and `.sdlc/discovery.json`; the workspace receives
`.sdlc/workspace-map.json` and `.sdlc/effective-config.json`. When no workspace source exists,
the installer also creates a manifest-owned `.sdlc/workspace.json` so subsequent runs discover
the selected workflow, roles and integrations. Existing workspace YAML/JSON stays user-owned.
Edits to a manifest-owned source are preserved and produce an ownership conflict on reinstall;
review/reconcile that source before continuing. Keep source policy in
`.sdlc/workspace.yaml` and repository overrides in `.sdlc/project.yaml`; discovery JSON is a
starting point, not a substitute for reviewed project commands.

Writes use atomic replacement, a workspace lock and a recovery journal. An interrupted transaction
rolls back on the next write operation; `--recover` performs explicit recovery, and
`--recover --dry-run` reports pending work without changing it. Unknown edits in a recovery target
block recovery rather than overwrite the edits. A write failure attempts immediate rollback.

Uninstall restores original files in reverse operation order and removes created files only when
hashes still match. Edits outside an unchanged managed Markdown block survive removal of that
block. Other user edits cause a conflict with no partial uninstall. Reconcile those files and
retry. `--uninstall codex` removes only that adapter and retains assets shared by other harnesses.
Installer metadata contains backups of merged instructions; treat it as project-private state.
The installer refuses path traversal and symlinked target components.

## Start work without accounts

Launch the chosen harness from a configured repository and ask:

```text
Implement the requirement in ./requirements/retry.md. Use the feature workflow, inspect
this repository's test commands, run relevant checks, review the result and deliver a local
patch. Do not access remote systems.
```

Prompt/local file requirements and local report/tree/patch/branch outputs work with no tracker or
MCP. Enable external connectors individually in configuration and use their native authenticated
CLI or MCP. Never put token values in workspace YAML; MCP environment bindings use `${VARIABLE}`
references (Codex requires matching names). Native policies are provider-specific and can be
affected by existing global settings. Generated prompts do not provide a sandbox; parallel writes
use the isolated coordinator rather than shared provider subagent working directories.

## Existing installations and commands

These entry points retain their original meaning and the legacy backup manifest:

```bash
./setup.sh --check
./setup.sh --pipeline
./setup.sh --list-installed
./setup.sh --uninstall pi
./setup.sh pi        # also qwen, crush, opencode, claude, omp
./setup.sh --plugin-mirror
```

Legacy no-target setup configures the kit checkout and may use the historical global pi directory.
Its backups live under `${SDLC_KIT_STATE_DIR:-~/.open-model-sdlc-kit}`. Prefer `--target` for new
workspaces. Legacy package installation now requires explicit `--allow-package-installs`; binaries
and packages are never installed automatically. Legacy five-column manifests remain readable;
new records add content hashes so uninstall can preserve later edits. Porters stage generated
assets before tracked copies, preserving pre-existing generated-file backups. `.env` remains
untracked and survives uninstall. `--pipeline` remains a compatibility roster reconciliation path;
new configurations use the role/workflow schema documented in [configuration](docs/configuration.md).

See [compatibility](docs/compatibility.md) and the native format contracts in `harnesses/` for
migration details. Run `bash scripts/check-kit.sh` for structural validation and the automated test
suite for disposable Go/Python/TypeScript discovery, provider rendering, rollback and legacy paths.
