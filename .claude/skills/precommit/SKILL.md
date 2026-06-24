---
name: precommit
description: >
  Use before committing or finishing a task: format, regenerate codegen, lint, test —
  in order, stopping on the first failure and fixing the cause. This is the local
  pre-merge gate that backs the Definition of Done. Invoke with /precommit for the full runbook.
---

# precommit — the local pre-merge gate

Run this from inside the service directory **before any commit and before reporting a task done**.
It is the ordered gate behind the Definition of Done (AGENTS.md §9). Run each step in order. The
moment a step fails, **stop, read the failure, fix the cause, and re-run that step** — do not press
on to the next step with a red one behind you.

`task precommit` runs the whole pipeline (fmt → codegen → tidy → lint → test) in one shot. The
ordered steps below are what it does; run them by hand when you want to see each gate fail in
isolation, or just run `task precommit`.

## Runbook (stop on first failure)

1. **Format** — `task fmt`
   gofumpt + gci. Fixes import ordering (`standard`, default, `prefix(github.com/acme)`,
   `localmodule`, blank, dot) and formatting. Always safe; run it first.

2. **Regenerate codegen IF its inputs changed.** Never hand-edit generated code — regenerate it.
   Re-run only the generators whose inputs you touched this task:
   - changed SQL in `db/queries/` or a migration schema → `task sqlc`
   - changed/added an interface that has a mock → `task mocks`
   - changed a `.proto` (in the contracts repo) → `task gen`
   - changed GraphQL schema/resolvers (GraphQL service only) → `task gqlgen`
   Then re-run `task fmt`, because codegen output gets formatted too. If you edited an interface,
   regenerate mocks *before* you lint or test — stale mocks fail to compile.

3. **Lint** — `task lint`
   golangci-lint v2 + govulncheck. Must be clean. Fix the root cause (line length ≤ 130, complexity,
   unused, error wrap with `%w`) — do not blanket-disable a linter to get green.

4. **Test (race detector on)** — `task test`
   `go test -race ./...`. Must pass. A flake or a real failure both block you: read the output and
   fix the cause. If the same test fails 2–3 times running and you cannot see why, stop and ask.

Single test while iterating: `RUN=TestName task test` (e.g. `RUN=TestGetProduct task test`). Always
finish with a full `task test` once the targeted one is green.

## Worked example — interface change, the right order

You added a method to the `Repository` interface and implemented the service that uses it.

```bash
task fmt          # 1. format
task mocks        # 2. interface changed → regenerate its mock (NEVER hand-edit mocks/)
task fmt          # re-format the regenerated mock
task lint         # 3. golangci-lint v2 + govulncheck — clean
task test         # 4. go test -race ./... — green
```

If step 4 reports `mock: I don't know how to return ... GetWarranty`, the mock is stale — you skipped
step 2 for the interface you changed. Re-run `task mocks`, then `task fmt`, then `task test`.

## Maps to the Definition of Done

Passing this gate ticks these boxes in AGENTS.md §9:
- `task fmt` applied, `task lint` passes, `task test` passes (race on).
- No hand-edited generated code; codegen re-run when its inputs changed (`task sqlc`/`mocks`/`gen`/`gqlgen`).

It does **not** verify the rest of §9 — no partial structs (§5), clean architecture (transport →
service → repository, never skipped), every task implemented with no stub/elision, verified APIs,
commit/branch conventions (§7). Confirm those yourself before you say "done".

## Reminder
Format → regenerate (if inputs changed) → lint → test. Stop on first failure and fix the cause, don't
skip ahead. Never hand-edit generated code. A green gate is necessary, not sufficient — §9 is the bar.
