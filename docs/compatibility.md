# SDLCkit 1.x → 2.0 compatibility

The migration changes the default product contract while preserving working entrypoints and optional capabilities. Existing project instructions are user-owned and remain authoritative; a migration preview must show conflicts rather than overwrite them.

| Existing interface | 2.0 behavior |
|---|---|
| `setup.sh pi/qwen/crush/opencode/claude/omp` | Retained legacy setup paths; models/auth inherit and integrations are optional |
| `setup.sh --check`, `--pipeline`, `--uninstall` | Retained; new target-aware modes share manifest-backed generation |
| `scripts/pipeline_config.py` queries | Same names/enabled/disabled/commands/count/check/json CLI; strict YAML/JSON, explicit malformed-input errors |
| `config/pipeline.yaml` | Legacy output roster remains authoritative for old porters; `config/roles.yaml` selects new native roles |
| `scripts/apply-pipeline.sh [--reconcile-only]` | Validates selection/regenerates adapters; no canonical `.md` → `.md.disabled` parking |
| pi/OpenCode/Qwen porters `[OUT_DIR]` | Same CLI/output formats; canonical neutral roles consumed through stable bridge; model inherited |
| planner/tech-designer/engineer/qa-lead names | Retained aliases for analyst/architect/implementer/verifier |
| go-code-reviewer/devops-lead/rlm | Preserved optional specialist aliases; generic reviewer is default |
| `/spec /clarify /plan /tasks /implement /test /review` | Composable neutral runbooks; selected recipe chooses needed stages |
| `/pr` | GitHub-specific `/deliver github_pr` alias; no authority bypass |
| Go/sqlc/testify/Serena/Jira skills | Preserved, conditional on relevant stack/enabled connector |
| `.claude-plugin` identifiers | Existing marketplace/plugin names preserved for installed users; descriptions/version updated |
| Local-model configs | Explicit v1 reference presets preserved under `profiles/local-model/`; active defaults no longer require an endpoint |
| Acme Go example | Historical instructions remain in `profiles/go/AGENTS.md` and the original reviewer in `profiles/acme-go/reviewer.md`; neither is imported by the active generic reviewer |

## Migrating configuration

Preview a neutral role map without writes:

```bash
python3 scripts/migrate-legacy.py config/pipeline.yaml
```

`--output PATH` creates a new JSON-compatible YAML document and refuses to overwrite an existing file. Review role selection and specialist opt-in. The helper does not migrate credential values, enable remote systems or move source instructions. New versioned workspaces use `config/defaults.yaml`/`schemas/workspace-v2.json`, with effective precedence/provenance visible via `config explain`.

New setup uses `--target`, `--harness`, `--profile`, `--dry-run`, `--non-interactive` and `--doctor`. The manifest records owned content/hashes; repeat installation is deterministic and uninstall preserves user changes. Legacy root-only manifests remain distinguishable from target-scoped manifests. See [INSTALL.md](../INSTALL.md) for exact recovery commands.

## Generated files and deprecation

Edit `roles/*.md`, then run `python3 scripts/render-role-bridges.py` and retained porters. Do not edit generated Claude role bodies or pi snapshots. A legacy selection filters legacy generated outputs without renaming canonical sources. Re-enable a legacy specialist with its existing pipeline `enabled: true`; the separate neutral default does not block that compatibility choice. New native target rendering uses effective `roles` configuration. Target native rendering chooses enabled roles using project/workspace configuration and owns only its manifest-tracked files.

No legacy porter, skill or command is removed in this migration. The v1 fixed eight-phase ceremony, mandatory Go/Jira/Serena/GitFlow assumptions and silent open-model routing are replaced by optional profiles and selected workflows. Historical design documents are marked historical and are not current default instructions. Provider-native formats evolve; doctor/smoke tests report actual supported/fallback/unavailable capabilities rather than claiming identical behavior.
