<!-- Phase 8 artifact. Use as the PR description body. Title: [WIP] [<TASK_ID>] <PR title>
     (drop [WIP] or open as a draft while unfinished). -->

## [<TASK_ID>] <PR title>

### What & why
<1–3 sentences. Link the Jira issue and the spec: specs/<TASK_ID>-<slug>/spec.md.>

### Changes (ordered)
1. ...
2. ...
3. ...

### How to verify
<Commands / grpcurl calls / steps a reviewer runs locally.>

### Pre-review checklist
- [ ] `task fmt` applied, `task lint` clean, `task test` green (race on).
- [ ] Clean architecture respected (transport → service → repository).
- [ ] No partial domain structs; no hand-edited generated code.
- [ ] No Russian in code; logging at the right level (warn/error only when actionable).
- [ ] Each acceptance criterion is covered by a test.
- [ ] Commit messages follow `<type>(<TASK_ID>): <desc>`.
- [ ] Branch off `develop`; not pushing to a protected branch.

### Extras
<Migrations to run, feature flags to flip, follow-up tickets, screenshots.>
