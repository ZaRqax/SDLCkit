---
description: Phase 6 (test) — the Definition of Done gate. Map every AC to a test, drive task fmt/lint/test green, then restate the DoD ticked.
argument-hint: <TASK_ID>
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

You are in **PHASE 6 — test** for **$1**. This is the **Definition of Done GATE**: nothing advances to
review until `task fmt`, `task lint`, and `task test` (race on) are all green and every acceptance
criterion has a passing test. State the phase, then work the steps below in order.

## 1. Read the prior artifacts
- `specs/$1-*/spec.md` — pull the acceptance criteria (AC-1, AC-2, …).
- `specs/$1-*/tasks.md` — confirm every task is checked off (implement phase done).
- `specs/$1-*/plan.md` — recall affected files / test suites.
If implement is unfinished, stop and say so — do not paper over it with tests.

## 2. Build / refresh `test-plan.md` — every AC maps to a test
Write `specs/$1-*/test-plan.md` from `templates/tasks-template.md`'s DoD shape. Make an explicit
AC → test table; **every AC must name at least one test that proves it**:

```
| AC    | Test (suite/case)                          | File                                  |
|-------|--------------------------------------------|---------------------------------------|
| AC-1  | ProductServiceSuite/TestGetProduct/found   | internal/service/product_test.go      |
| AC-2  | ProductServiceSuite/TestGetProduct/notfound| internal/service/product_test.go      |
```

Any AC with no test is a **gap** — write the missing test now (testify, table-driven, AAA), mirroring
the existing suite style in AGENTS.md §4:

```go
func (s *ProductServiceSuite) TestGetProduct() {
    tests := []struct {
        name    string
        id      string
        mockFn  func(*mocks.Repository)
        want    domain.Product
        wantErr bool
    }{
        {name: "notfound", id: "x", mockFn: func(r *mocks.Repository) {
            r.On("GetProduct", mock.Anything, "x").Return(domain.Product{}, repository.ErrNotFound)
        }, wantErr: true},
    }
    for _, tt := range tests {
        s.Run(tt.name, func() {
            repo := mocks.NewRepository(s.T())
            tt.mockFn(repo)
            got, err := service.New(repo).GetProduct(context.Background(), tt.id)
            if tt.wantErr { s.Require().Error(err); return }
            s.Require().NoError(err)
            s.Equal(tt.want, got)
        })
    }
}
```

If you changed an interface, regenerate mocks first — never hand-edit `mocks/`: `task mocks`.

## 3. Drive it green (in this exact order)
Run from inside the service directory:

```bash
task fmt    # gofumpt + gci; commit-ready formatting
task lint   # golangci-lint v2 + govulncheck — must pass clean
task test   # go test -race ./... — must pass clean
```

Single-test loop while fixing: `RUN=TestGetProduct task test`.

**A failing test means the CODE is wrong — fix the code, not the test.** Never weaken an assertion,
delete a case, or `s.T().Skip()` to go green. The only time you change a test is when the test itself
encodes the wrong expectation versus the spec's AC — and then you cite the AC. If a test fails 2–3
times and you can't see why, **stop and ask one clear question** (AGENTS.md §0.6).

Watch for the team's #1 bug while fixing: **no partial structs** — if a test surfaces a zero-value
field, fill every field or fix the source mapper/SQL (AGENTS.md §5), don't `mock.Anything` around it.

## 4. GATE — restate the Definition of Done, every box ticked
Do **not** advance to `/review` until all of these are literally true for $1:

- [ ] Every item in `tasks.md` is implemented — no TODO, no stub, no elision.
- [ ] Every AC in `spec.md` maps to a passing test in `test-plan.md`.
- [ ] No partial domain struct introduced (§5).
- [ ] No hand-edited generated code; `task sqlc`/`mocks`/`gen` re-run if their inputs changed.
- [ ] `task fmt` applied, `task lint` passes, `task test` passes (race detector on).
- [ ] Clean architecture respected: transport → service → repository, never skipped (§3).
- [ ] Every new/changed symbol verified to exist (no hallucinated APIs).
- [ ] Commit message + branch follow §7 (`feat(<TASK_ID>): …` / `<type>/<TASK_ID>-<desc>`).

If any box is unchecked, **say which and why, and ask** — do not report success. When all are ticked,
update the `tasks.md` DoD section and hand off: phase 6 complete, ready for `/review`.
