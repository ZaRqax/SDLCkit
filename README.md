# SDLCkit 2.0

**A configurable SDLC workspace for Codex, Claude Code, OpenCode and Cursor.** Bring an existing repository, a requirement from chat/file/issue, and the output you want. The kit discovers conventions, chooses an appropriate workflow, verifies changes and delivers a report, patch, local commit/branch, GitHub PR or GitLab MR.

The kit can remain in `~/tools/SDLCkit` while projects stay anywhere in your approved workspace. It supports Python, TypeScript, Go and other repositories through their existing tools. Jira, Confluence, GitHub, GitLab, Serena, MCP servers and model endpoints are optional. Smaller/local models and legacy pi/Qwen/Crush/omp entrypoints remain available.

## Start with an existing workspace

Read [INSTALL.md](INSTALL.md) for prerequisites and the deterministic installer. Python dependencies are declared in `requirements.txt`; install them in your chosen environment when needed. Nothing installs packages or launches workers silently.

```bash
# Preview scoped files and conflicts first; project repositories stay in place.
./setup.sh --target /workspace/projects --harness codex --dry-run
./setup.sh --target /workspace/projects --harness codex --non-interactive
./setup.sh --target /workspace/projects --doctor
```

For agent-led setup paste the [onboarding prompt](docs/onboarding.md) into a primary harness. It uses the same installer/manifest as the script path. Existing `AGENTS.md`, hooks and configuration are preserved; generated ownership makes updates and uninstall reviewable.

Then ask your agent:

> Implement `./requirements/retries.md` in billing-api. Follow its existing conventions, run relevant checks, and leave a local patch. Do not access remote systems.

Or normalize work using the local CLI:

```bash
python3 scripts/sdlc.py intake 'Add stable sorting to the results' --source prompt --root /workspace/projects --delivery patch
python3 scripts/sdlc.py config explain /workspace/projects/.sdlc/workspace.json
```

## Independent choices

| Choice | Options |
|---|---|
| Harness | Codex, Claude Code, OpenCode, Cursor; legacy pi/Qwen/Crush/omp |
| Requirement | Chat, local Markdown/text/PDF through supported tools, repository docs, URL or enabled issue/wiki/MCP connector |
| Workflow | Quick fix, feature, cross-repo, investigation, high-risk |
| Delivery | Report, working tree, patch, local commit/branch, explicitly authorized GitHub PR or GitLab MR |

A quick fix needs a short goal/checklist and targeted tests. A feature gets a short design and review. Cross-repository work uses dependency ordering and isolated worktrees. Investigation creates a report without product code or commits. User/project policy determines conditional approval gates; there is no universal eight-stage ceremony.

## What ships

- [Universal contract](AGENTS.md), [workflow recipes](FLOW.md), neutral [role library](roles/) and optional [Go profile](profiles/go/).
- Read-only discovery, deterministic native harness adapters, ownership manifest, dry-run, doctor and safe uninstall.
- Versioned configuration/schema validation, effective settings/provenance, explicit path allowlists and non-weakening safety policy.
- [Requirements and delivery adapters](docs/connectors.md), source provenance, bounded untrusted input and local-first outputs.
- [Durable local orchestration](docs/orchestration.md): dependency tasks, isolated workers, recorded verification, retries/cancellation, explicit watches and audit events. Opt-in only.
- [Legacy compatibility](docs/compatibility.md), reusable Go/Jira/Serena skills and optional read-only RLM/graph analysis.

## Safety and verification

Remote reads use only enabled connectors; external writes require scoped authorization. A patch request never pushes or opens a PR. No automatic issue transitions, merge or deployment. Native agent permissions and project policies remain in force. Missing tools, failed tests and unsupported provider features are reported honestly; generated fixtures do not certify live external accounts.

```bash
bash scripts/check-kit.sh
python3 -m unittest discover -s tests -v
```

See [onboarding](docs/onboarding.md), [connectors](docs/connectors.md), [workflows](docs/workflows.md), [orchestration](docs/orchestration.md), [compatibility](docs/compatibility.md), [maintainer architecture](KIT-DEV.md), and the [Russian overview](docs/readme-ru.md). Licensed under [MIT](LICENSE).
