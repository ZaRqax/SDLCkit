# Spec: work-20261015 — Frontier-agent migration

- **Source:** user-provided `SDLCkit_Frontier_Agent_Migration_Plan.md`, sections 1–18.
- **Source SHA-256:** `7ab997af592d73b5e984c52d2a0807870ee7e80476907347d99a855d06997155`.
- **Type:** feature.
- **Status:** IMPLEMENTED; acceptance evidence in test-report.md and review.md.
- **Delivery:** one separate local commit; no push, PR/MR creation, issue mutation or deployment.

## Problem and goal

The kit currently assumes an Acme Go workspace, Jira, Serena, GitFlow and eight mandatory phases.
Migrate it into a configurable workspace harness for Codex, Claude Code, OpenCode and Cursor,
with optional legacy harnesses, integrations, isolated parallel execution and durable orchestration.
Projects must remain in their existing directories; the kit can be installed elsewhere.

## Scope

The user explicitly selected the entire six-part roadmap, including the orchestrator and parallel
execution, rather than only the initial documentation/onboarding milestones. The roadmap's PR
numbers define implementation slices; delivery remains a single local commit as requested.
Implement local tooling and documented adapter contracts, not a hosted workflow SaaS.
Retain legacy installers, porters, skills, Go reviewer, graph documentation and read-only RLM.
Optional connectors must report unavailable capabilities honestly. No external accounts or
credentials are required for offline operation or the default automated test suite.

## Acceptance criteria

- **AC-1:** Default instructions and templates work with prompt/file requirements and Python,
  TypeScript or Go projects, without mandatory tracker, git provider, branch model or MCP server.
- **AC-2:** Discovery inventories repositories, worktrees/submodules, conventions, commands and
  existing instruction/config files without executing project code or reading secret values.
- **AC-3:** Shared installer logic supports target/harness/profile/dry-run/non-interactive/doctor;
  dry-run writes nothing, repeated setup is deterministic, and scoped uninstall preserves edits.
- **AC-4:** Versioned configuration validates syntax, schema, references, path confinement,
  capabilities and policy; effective configuration explains precedence and provenance.
- **AC-5:** Codex, Claude, OpenCode and Cursor receive native scoped assets and capability/version
  reports. Existing files require a safe merge or a reported conflict. Models inherit by default.
- **AC-6:** Prompt/file intake produces a stable WorkItem with provenance. Enabled remote source
  adapters use bounded retrieval; unsupported adapters fail explicitly; retrieved text is data.
- **AC-7:** Delivery supports report, working tree, patch, commit, branch, GitHub PR and GitLab MR.
  Remote publishers require explicit authorization and reconcile retries; patch is local only.
- **AC-8:** Quick-fix, feature, cross-repo, investigation and high-risk workflows use validated
  dependencies and conditional gates. Skipped/unavailable/failed checks never count as passed.
- **AC-9:** Neutral roles generate runtime assets; legacy setup/check/pipeline/uninstall and porter
  entry points remain regression-tested; optional Go conventions remain discoverable.
- **AC-10:** Durable run/task/event state records input revisions, dependencies, owners, attempts,
  verification evidence and outcomes; interruption, failure, retry and resume are recoverable.
- **AC-11:** Parallel writers use distinct worktrees/clones with bounded concurrency, leases and
  repository coordination. Dependency order, cancellation and combined verification are enforced.
- **AC-12:** Explicitly enabled polling/webhook intake uses a persistent deduplicated queue,
  eligibility rules, resource limits and status CLI. Disabling intake prevents new launches while
  retaining state. Installation never launches workers or watchers automatically.
- **AC-13:** Effect-based policy distinguishes observe/local/remote actions, protects secrets and
  generated paths, confines writes and rejects unauthorized external effects or unsafe overrides.
- **AC-14:** Automated disposable-repository tests cover source plan matrix A–N where feasible,
  including conflicts, interrupted installation, concurrency, worker crashes and publication
  ambiguity. Provider/account-dependent live checks are reported separately from offline tests.
- **AC-15:** Documentation, CI, hooks, compatibility notes and examples describe shipped behavior;
  all required available checks pass and the full migration is delivered as one local commit.

## Affected repositories and contracts

Only this kit repository is changed. Temporary sample repositories are test fixtures. New local
configuration, WorkItem, run/event, connector, harness and delivery contracts belong to the kit;
there are no product-service database/proto migrations.

## Clarifications

- **Resolved:** user requested the entire plan, including orchestration and parallel execution.
- **Resolved:** the requested deliverable is a separate commit, not six remote PRs.
- **Resolved:** use an internal work ID; no Jira issue exists or is fabricated.
- **Resolved:** user explicitly approved full implementation in chat.

## Risks and verification limits

Provider formats evolve; verify against installed CLIs and official documentation before coding.
External publisher/source behavior can be tested with controlled command/API doubles without
mutating accounts. Real remote publication and paid model execution require separate authorization.
The current repository has no Taskfile or Go module: use its actual structural verifier, Python
tests, syntax/config checks and CI requirements rather than inventing service commands.

## Acceptance review

- [x] Goal and full roadmap scope recorded.
- [x] Acceptance criteria are observable.
- [x] Delivery and external-action boundaries are explicit.
- [x] Affected repository and new contract categories identified.
- [x] Task checklist approved before implementation.
