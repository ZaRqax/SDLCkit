<!-- Phase 4 artifact. Copy to specs/<TASK_ID>-<slug>/tasks.md. Reads plan.md.
     Tasks must be SMALL, ORDERED, dependency-aware, and traceable to ACs.
     [P] = can run in parallel with other [P] tasks at the same step.
     The human approves this file BEFORE implementation starts. -->

# Tasks: <TASK_ID> — <short title>

- **Plan:** ./plan.md
- **Status:** DRAFT → APPROVED → IN_PROGRESS → DONE

## Task list (check off as you go — this is your external memory; update after every task)
- [ ] **T1** — <smallest sensible change> — covers AC-1 — files: `...`
- [ ] **T2 [P]** — <independent change> — covers AC-2 — files: `...`
- [ ] **T3** — depends on T1 — covers AC-1 — files: `...`
- [ ] **T4** — write/extend testify suite for T1–T3 — covers AC-1,AC-2
- [ ] **T5** — `task fmt && task lint && task test` green (Definition of Done gate)

---
## Self-contained story files (BMAD pattern — one per task; pack everything the implementer needs)

### T1 — <title>
- **Goal:** <one sentence>
- **AC covered:** AC-1
- **Files to touch (verified):** `internal/service/foo.go`, `internal/service/foo_test.go`
- **Relevant existing symbols:** `service.Foo`, `repository.FooStore` (confirm with Serena find_symbol)
- **Constraints:** no partial structs; transport→service→repository; testify table-driven test.
- **Done when:** AC-1's behavior is observable and its test passes.
- **Notes / gotchas:** <e.g. regenerate mocks after changing the interface: `task mocks`>

### T2 — <title>
<same block...>

---
## Definition of Done (restate, ticked, before declaring complete)
- [ ] All tasks above checked.
- [ ] No stub / TODO / elision; no partial structs.
- [ ] Generated code regenerated, not hand-edited.
- [ ] `task lint` + `task test` pass (race on).
- [ ] Each AC has a passing test.
