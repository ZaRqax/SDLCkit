# Workflows sized to the task

A workflow is independent of harness, model, requirement provider and delivery. Recipes live in `config/workflows/`. Choose from verified scope and risk; explicit user constraints such as plan only, patch only or no remote access remain authoritative.

| Recipe | Selected stages | Evidence |
|---|---|---|
| quick-fix | intake → context → execute → verify → deliver | Short goal/checklist, diff and targeted results |
| feature | intake → context → design → execute → verify → review → deliver | Source/ACs, concise plan/tasks, checks, findings and result |
| cross-repo | feature stages with dependency DAG | Project/worktree ownership, contract/integration evidence and coordinated outputs |
| investigation | intake → context → analysis → deliver | Findings, source references and report; no product edits or commits |
| high-risk | feature stages with explicit risk gates | Design plus scoped data/infrastructure authorization and relevant evidence |

Clarification and approval are conditional gates. Ask only blocking questions; retain engineering assumptions with evidence. Reuse existing approval within its scope. No separate agent is required for each role or harmless stage.

## Exact recipe grammar

Each version-1 recipe declares `id`, `stages` (`id`, canonical `role`, `needs`, `when`), `quality.required` and `gates`. Dependencies must exist and form a DAG. Shipped recipes use `when: always`; `sdlc.config.load_workflow` validates fixed conditions `always`, `nontrivial`, `requires_review`, `high_risk`. Runtime adapters also validate their supported bounded predicates; no arbitrary Python/JavaScript evaluation is allowed. A skipped conditional stage remains skipped with a reason; it cannot manufacture evidence for a required gate.

## Artifacts and resumption

For substantial work use `specs/<work-id>-<slug>/` with spec/plan/tasks, a readable handoff and verification/review/delivery evidence. Stable IDs are internal; upstream issue IDs remain optional references. `specs/INDEX.md` tracks project/workflow/state/output and update time. Runtime state and event records live locally under `.sdlc/` by default, not in a mandatory tracker.

Record planned, running, passed, failed, skipped, unavailable and not-run distinctly. Resume from the saved revision, task status and attempt; never mark missing work completed. Worker crashes and publication uncertainty need different recovery: retry a failed isolated worker, but reconcile an uncertain publication before attempting a second create.

## Commands and gates

Retained `/spec`, `/clarify`, `/plan`, `/tasks`, `/implement`, `/test` and `/review` are composable runbooks, not forced phases. `/deliver` chooses the requested output; `/pr` remains the GitHub-specific alias and does not grant remote authority. Codex and other harnesses can read these runbooks without assuming Claude slash-command support.

Always run relevant target-repository checks and record actual exit codes. A project may require stronger approvals/checks, while kit invariants cannot weaken: no secret exposure, destructive effects, shared-tree writers, auto-merge or production deployment. External writes and risky data/infrastructure actions retain authorization gates. See `config/security-policy.yaml`, `sdlc/policy.py` and [orchestration](docs/orchestration.md).
