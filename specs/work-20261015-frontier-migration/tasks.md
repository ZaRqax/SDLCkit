# Tasks: work-20261015 — Frontier-agent migration

- **Plan:** [plan.md](plan.md).
- **Status:** DONE — full implementation, review and local commit delivery.
- **Delivery:** one local commit containing all six roadmap slices; no remote publication.
- **Ordering:** execute in order unless marked `[P]`; parallel tasks require disjoint ownership
  and isolated working copies, followed by integration/review in the primary working copy.

## 1. Universal core (roadmap PR 1)

- [x] **T01** — Rewrite `AGENTS.md`, `KIT-DEV.md`, `FLOW.md`, `README.md`, `CONTRIBUTING.md`
  around project conventions, task-sized recipes, source/delivery neutrality and evidence. Preserve
  Acme/Go examples in an optional profile. **AC-1, AC-9, AC-13.**
- [x] **T02** — Generalize spec/plan/tasks/handoff/delivery templates and run index; document
  compatibility/deprecations, shipped capabilities and the internal work-ID convention.
  **AC-1, AC-8, AC-9, AC-15.**

## 2. Onboarding and installation (roadmap PR 2)

- [x] **T03** — Define versioned workspace/project/role/workflow/policy schemas, defaults, merge
  semantics and validation. Implement explain/provenance and legacy config migration with explicit
  errors for unsupported syntax. **AC-4, AC-8, AC-13.**
- [x] **T04** — Implement read-only discovery for arbitrary external roots, repositories,
  worktrees/submodules, stacks, commands, branches and existing configs; no secret-value reads or
  project-code execution. **AC-2.**
- [x] **T05** — Implement deterministic render plans, preview diff, path confinement, ownership
  hashes, atomic writes, journal recovery, conflict handling and edit-preserving uninstall.
  **AC-3, AC-4, AC-13.**
- [x] **T06** — Add native Codex/Claude/OpenCode/Cursor adapters, capability probes and snapshots;
  inherit models and emit only enabled integrations. Verify installed CLI formats and document
  unsupported capabilities. **AC-5, AC-9.**
- [x] **T07** — Extend `setup.sh` with target/harness/profile/dry-run/non-interactive/doctor/help;
  route agent/script setup through the same core. Retain check/pipeline/list/uninstall and all
  legacy positional invocations. Document Linux/macOS/WSL and native Windows limits. **AC-3, AC-9.**
- [x] **T08** — Replace mandatory MCP/env defaults with optional presets; update install and
  multi-repo adoption guides and provide the one-prompt onboarding path. **AC-1, AC-5, AC-13.**

## 3. Requirement and delivery adapters (roadmap PR 3)

- [x] **T09 [P]** — Define normalized WorkItem/SourceDocument/evidence contracts; implement prompt,
  local-file and URL intake plus enabled tracker/docs/custom connector routing. Preserve revisions,
  bound related retrieval and fail explicitly when a capability/tool is unavailable. **AC-6, AC-13.**
- [x] **T10 [P]** — Implement report/tree/patch/commit/branch delivery plus authorized GitHub PR
  and GitLab MR publishers with prepare/validate/publish/reconcile and durable idempotency records;
  no remote side effects for local delivery. **AC-7, AC-10, AC-13.**
- [x] **T11** — Introduce generic `/deliver`, retain `/pr` as a GitHub alias; generalize existing
  source/planning/implementation/test/review commands and optional integration skills.
  **AC-1, AC-6, AC-7, AC-9.**

## 4. Recipes, roles and state (roadmap PR 4)

- [x] **T12** — Define canonical neutral roles, optional specialists, recipe dependencies and
  finite conditions; generate runtime agents without model pins. Adapt legacy porters via stable
  inputs and regenerate affected snapshots. Stop using source-file parking as the new core toggle.
  **AC-5, AC-8, AC-9.**
- [x] **T13** — Persist run/task/event/attempt/evidence states; validate transitions and resume
  behavior; capture actual verification commands/exit codes and review findings. Skipped checks and
  failed checks remain explicit. **AC-8, AC-10.**

## 5. Safe parallel execution (roadmap PR 5)

- [x] **T14** — Implement dependency readiness, isolated worktree/clone allocation, repository
  coordination and bounded subprocess workers; persist ownership/revisions/leases. **AC-10, AC-11.**
- [x] **T15** — Implement cancellation, lease/crash recovery, bounded retry, integration evidence
  and coordinated multi-delivery reconciliation. Separate write workers from read-only RLM.
  **AC-7, AC-10, AC-11.**

## 6. Opt-in orchestration (roadmap PR 6)

- [x] **T16** — Implement persistent deduplicated queue, approved polling/webhook intake,
  eligibility rules, resource/time/budget/log limits and launch authorization. Watchers disabled by
  default; stopping intake preserves existing runs. **AC-10, AC-12, AC-13.**
- [x] **T17** — Add status/history/retry/cancel/stop CLI and orchestration/runbook documentation,
  including permission limits, recovery, unavailable providers and optional graph/RLM relationship.
  Update plugin metadata without breaking existing plugin identifiers. **AC-9, AC-10, AC-12, AC-15.**

## 7. Enforcement, verification and delivery

- [x] **T18** — Align executable effect policy, harness permissions, hooks and CI; test denial of
  unsafe overrides, path escapes, unauthorized external actions and secret exposure. Respect target
  generated patterns and existing hooks. **AC-4, AC-5, AC-13.**
- [x] **T19** — Automate source matrix A–N with disposable Go/Python/TypeScript repositories;
  cover dry-run/idempotency, preserved instructions, paths with spaces, interrupted writes,
  uninstall conflicts, legacy regression, same-repo writers, dependency order, crashes, failed
  verification, publication ambiguity and malicious source content. **AC-1–AC-14.**
- [x] **T20** — Run structural verifier, Python suite, syntax/schema checks and provider CLI
  smoke tests; repair blockers and record real exit codes and unavailable live checks. Review
  spec/plan/tasks/final diff and update handoff/index. **AC-14, AC-15.**
- [x] **T21** — Create the requested single local commit on a dedicated branch, verify its file
  list and final status, and report commit ID, changes, checks and material limits. **AC-15.**

## Definition of Done

- [x] Every task above implemented; no placeholder functionality or falsely completed stages.
- [x] No incomplete domain/data mapping introduced.
- [x] Generated assets regenerated from verified sources.
- [x] Actual kit checks and test suite pass; no invented Taskfile/Go-module checks.
- [x] Module responsibilities and project isolation respected.
- [x] New APIs/configuration verified against source, tests and provider documentation.
- [x] One requested local commit created; no push or remote PR is required for this delivery.

## Approval

Approved in chat: implement the entire supplied migration and change the kit approach completely. Approval covers this local implementation and its tests; it does not authorize package
installation, remote writes, live account mutations, migrations, deployments or background watches
against real external systems.
