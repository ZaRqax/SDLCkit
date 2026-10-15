# Recipes, roles and evidence

[FLOW.md](../FLOW.md) defines the selected logical stages and [config/workflows](../config/workflows/) contains versioned recipes. Quick fixes use short checklists; substantial features/cross-repo changes use enough design and dependency detail to verify the outcome. Investigations produce evidence/reports without product edits. High-risk work adds scoped approval gates.

Neutral [roles](../roles/) declare purpose, capabilities, allowed effects, outputs and handoff. They inherit the user's model. One agent can perform multiple low-risk roles; optional reviewers/specialists load only when relevant. The preserved Go microservice conventions and deep reviewer live in [profiles/go](../profiles/go/), while reusable legacy skills remain discoverable under `.claude/skills/`.

Version-1 recipes use a dependency DAG with stable stage IDs, role references and deterministic conditions. Shipped files use `when: always`. The core fixed vocabulary is always, nontrivial, requires_review and high_risk; runtime validates its additional bounded predicate forms. Arbitrary code evaluation is forbidden. Record skipped stages explicitly with the reason, preserving prerequisite/quality checks.

For long work keep readable spec/plan/tasks/handoff and machine state. Record source revisions, input git revisions, task/worktree owners, attempts, command exits, actual review findings and delivery references. Resume from saved state, not an optimistic checklist. Failed/unavailable/skipped/not-run outcomes cannot silently become passed.

User requests like plan only, implement my approved plan, skip an unnecessary formal spec, no remote access and patch delivery are supported. Project policies can require stronger review/approval; they cannot waive inherited safety. Existing authorization persists within scope. See [runtime/README.md](../runtime/README.md) for the executable plan and condition grammar.
