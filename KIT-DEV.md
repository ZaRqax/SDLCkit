# KIT-DEV.md — SDLCkit architecture and maintenance

SDLCkit is a frontier-agent-native SDLC workspace. Codex, Claude Code, OpenCode and Cursor are primary harnesses; smaller/local models and pi, Qwen, Crush and omp remain compatible. The product is task intake → appropriate workflow → verified, reviewable output for an existing repository in any supported stack. No tracker, git host, model endpoint, Go toolchain or MCP bundle is required.

## Architectural invariants

- WorkItem, Workspace, Role, Harness, Workflow, Integration and Delivery are independent contracts. `AGENTS.md` contains the universal verify-first/scope/evidence/safety contract; nearest project instructions retain repository-specific authority.
- `roles/*.md` is the neutral canonical role source; `skills/` contains canonical reusable runbooks, mirrored to `.claude/skills/` for compatibility. Frontmatter declares id, purpose, capabilities, allowed_effects, outputs and handoff. Models inherit. `scripts/render-role-bridges.py` derives retained Claude bridges; legacy porters consume the stable `scripts/role_library.py` bridge. Do not hand-edit generated role bodies or pi snapshots.
- `config/defaults.yaml` and `schemas/workspace-v2.json` define effective configuration. YAML uses PyYAML and validation uses jsonschema (`requirements.txt`); JSON parsing uses the standard library, but validation still requires jsonschema. Missing dependencies produce explicit actionable errors; setup never installs them silently.
- Configuration maps merge by key; named role lists merge by id; deny lists union; command and ordinary lists replace. Defaults are followed by workspace/local overrides and selected project policy. Inherited safety cannot weaken. Explicit repository instructions are preserved as instructions, never interpreted as executable YAML. `config explain` shows effective settings and winning provenance.
- Relative project paths resolve against declared workspace root. Resolve symlinks and enforce workspace/explicit allowed_paths before generating or running. No repository relocation, global credential ceremony or silent overwrite of user files.
- Agent-led and `setup.sh` onboarding share discovery, rendering, manifest and uninstall logic. Dry-run is read-only; generation is deterministic; uninstall preserves user edits. Provider-specific assets must be scoped to selected projects/harnesses. Native runtime features remain version-sensitive and doctor reports actual installed capabilities.
- Connectors are disabled by default. Source content remains lower-trust data with bounded retrieval/provenance. Delivery defaults to local working_tree; publishing needs enabled capability and scoped authorization. Duplicate uncertain publication must reconcile before retry.
- Effects are governed by `sdlc/policy.py`, native harness permissions and repository checks. This is defense in depth, not a claim that regex can sandbox arbitrary shell programs. No automatic merge, production deploy, force push, destructive wipe or secret exposure.
- Durable local runtime state records task dependencies, owners, isolated worktrees, revisions, leases, attempts, events, verification and delivery references. Parallelism/watchers are explicit opt-in; installation never starts a daemon. RLM remains bounded read-only research and the optional graph engine remains analysis, neither is the coordinator.

## Compatibility and validation

Preserve `setup.sh`, its legacy positional harness calls and --check/--pipeline/--uninstall, existing porters, reusable Go skills and plugin identifiers. `config/pipeline.yaml` is a compatibility roster; enablement filters generated outputs, never parks canonical role sources. See `docs/compatibility.md`.

Run structural checks and the automated unittest suite. Tests use disposable Go/Python/TypeScript repositories and fake provider processes to verify actual command exits, dry-run/idempotency/uninstall behavior, optional connectors, effect guards, workflow state, isolated concurrency, recovery and delivery reconciliation. Installed-provider probes must report unsupported capabilities honestly; fixture success is not proof of a live account publication.

Useful maintainer commands:

```bash
python3 scripts/validate-config.py --explain
python3 scripts/render-role-bridges.py --check
python3 agents-config/pi/port-agents.py
bash scripts/check-kit.sh
python3 -m unittest discover -s tests -v
```
