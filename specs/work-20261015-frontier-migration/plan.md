# Plan: work-20261015 — Frontier-agent migration

- **Spec:** [spec.md](spec.md).
- **Status:** IMPLEMENTED; verified against the final integrated change.

## Architecture

Keep `setup.sh` and the legacy porters as compatibility entry points. Add a small Python local
core with explicit contracts for configuration, discovery, rendering/ownership, requirements,
workflow state, policy, delivery and runtime coordination. Thin scripts expose the shared engine
to agents and shell users; CLI and agent onboarding must not maintain separate generation logic.
Use SQLite for durable orchestration state and transactions, JSON for machine evidence, Markdown
for human handoffs, and validated versioned YAML/JSON configuration. Use existing Python tools;
any dependency installation requires approval and is not part of automatic onboarding.

## Configuration and ownership

Safety invariants cannot be weakened. Target repository rules precede workspace/local overrides,
selected profile and defaults. Merge maps by key and named roles by ID; union deny rules. Resolve
project paths from the declared workspace root, reject escaping/symlink targets, and expose values
with provenance through doctor/explain. Existing instructions, hooks and provider configs remain
user-owned. Preview changes first; atomically write only owned files or explicitly merged regions,
record original content/hash and generated hash, and refuse conflicting installs/uninstalls.
Recovery journals must distinguish completed writes from interrupted writes.

## Requirement and delivery contracts

Define SourceDocument/WorkItem before implementing prompt/file and optional provider adapters.
Connectors declare identify/fetch/search/related/write capabilities; disabled capabilities cannot
be invoked. Preserve source revisions, bounded related evidence and trust classification. Local
delivery is the default; GitHub/GitLab publishers separately prepare, validate, publish and
reconcile with persisted idempotency markers. Authorization is explicit and effect-scoped, never
inferred from a repository remote or lower-trust source body. Reconcile ambiguous remote outcomes
before retries; report missing tools/auth without inventing output.

## Workflows and runtime

Canonical roles live under `roles/`; runtime adapters render only enabled roles and integrations.
Recipes use a finite validated condition vocabulary rather than evaluating arbitrary expressions.
Persist run/task state transitions, dependency edges, attempts, leases, input revisions, command
exit codes, evidence and publication records. Schedule ready tasks into isolated worktrees/clones,
with bounded workers and repository coordination. Reclaim crashed leases safely, cancel process
groups, retain failed verification and perform aggregate contract review before delivery.
Opt-in polling and authenticated webhook intake feed the same durable deduplicated queue.
Eligibility rules, concurrency/time/budget/disk/log limits and stop controls apply to new launches;
status CLI exposes current and historical state. Installation never starts background processes.

## Verified existing files and planned additions

| Area | Existing files inspected | Planned change/additions |
|---|---|---|
| Rules/docs | `AGENTS.md`, `KIT-DEV.md`, `CONTRIBUTING.md`, `FLOW.md`, `README.md`, `INSTALL.md` | Rewrite generic core; optional Go profile; onboarding/workflow/connector/orchestration/compatibility docs |
| Installer | `setup.sh`, `.gitignore` | New flags routed to shared engine; preserve legacy paths and generated ownership |
| Roster | `config/pipeline.yaml`, `scripts/apply-pipeline.sh`, `scripts/pipeline_config.py` | Compatibility reconciliation plus new defaults, roles, recipes, schemas and migration helper |
| Verification | `scripts/check-kit.sh`, `.githooks/pre-commit`, `.github/workflows/ci.yml` | Core/schema/harness/runtime/legacy checks; stack-specific optional checks |
| Artifacts | `templates/{spec,plan,tasks,pr,handoff}-template.md`, `specs/INDEX.md` | Generic IDs/sources/deliverables/evidence and explicit state |
| Harnesses | `.claude/{agents,commands,skills}`, `agents-config/`, `CLAUDE.md` | Read each affected source before editing; add native adapters under `harnesses/` and regenerate snapshots |
| Policy | `config/security-policy.yaml`, `.mcp.json`, `.env.example` | Effect-scoped policy, disabled integrations, optional credentials; inspect settings/hooks before editing |
| Local core | New | Shared Python modules and discover/render/validate/intake/deliver/runtime CLI scripts |
| Runtime | New | Durable task/queue/event storage, worktree manager, subprocess adapters, watcher/webhook/status CLI |
| Tests | New | Disposable Go/Python/TS repos, command/provider doubles, installer/state/concurrency failure injection |

New paths above are proposals, not claims of existing APIs. Existing source files listed by directory
will be read individually before editing. Preserve Go specialist skills and the read-only graph/RLM
features; do not hand-edit generated pi snapshots or other generated runtime assets.

## Test strategy and release

Run `bash scripts/check-kit.sh` (baseline passed), Python unit/integration tests, shell/Python/JSON/
YAML syntax/schema checks, deterministic harness snapshots and documented CLI smoke tests. Map
every AC to evidence. Use temporary repositories and controlled remote doubles for matrix A–N.
Probe installed provider versions; distinguish actual CLI parsing from fake-worker tests and live
authenticated model execution. No check may silently convert a failure or skipped stage to success.
Review spec/plan/tasks against the final diff; regenerate affected snapshots and run checks once more
after any repairs. Create one dedicated local feature branch and one commit after verification;
do not push or create a remote PR. Record any unavailable live checks as limitations.

## Plan checklist

- [x] Every acceptance criterion has an implementation area and verification strategy.
- [x] No product-service architecture or database migration is needed.
- [x] Existing entry points and generated-source boundaries identified.
- [x] Isolation, rollback, authorization and recovery covered.
- [x] Tasks approved before implementation.
