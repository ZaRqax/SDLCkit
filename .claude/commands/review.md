---
description: Phase 7 (review) — review the diff against the kit checklist and cross-check spec↔plan↔tasks↔code for drift.
argument-hint: <TASK_ID>
---

You are in **PHASE 7 — review** for **$1**. The gate (AGENTS.md §9 Definition of Done): **every
blocker you find must be fixed before `/pr`.** Review notes are an artifact, not the goal — a clean
diff is.

**Claude only:** delegate this entire phase to the **go-code-reviewer** subagent (pass `$1` and the
spec dir). Open agents: run the steps below yourself.

## Workflow

1. **Locate artifacts.** Find the spec dir: `ls specs/$1-*/`. Read `spec.md` (acceptance criteria),
   `plan.md` (intended files/contracts), `tasks.md` (checklist). These are the contract you review
   the code against.

2. **Get the diff.** Run it; read every hunk.
   ```bash
   git fetch origin develop -q
   git diff --stat origin/develop...HEAD
   git diff origin/develop...HEAD          # read all of it, not just the stat
   ```

3. **Review against the checklist.** For each hunk, check:
   - **Clean architecture** — transport must NEVER call a repository directly (AGENTS.md §3). A
     `*Handler` reaching for `h.repo.Get(...)` instead of `h.svc.Get(...)` is a blocker.
   - **No partial structs** (§5) — any `domain.X{...}` literal that omits fields is a blocker.
     ```go
     return domain.Product{ID: id, Name: name}   // ❌ Price, SKU silently zero — blocker
     ```
   - **No hand-edited generated code** — changes under `repository/postgres/sqlc/`, `mocks/`, or
     `gen/` are a blocker. The fix is to edit the SQL/proto/interface and re-run `task sqlc`/`task
     mocks`/`task gen`, never the generated file.
   - **Error wrapping** — non-sentinel returns wrap with `%w` + lowercase context, no trailing
     punctuation: `fmt.Errorf("get product %q: %w", id, err)`.
   - **gci import order** — `standard`, default, `prefix(github.com/acme)`, localmodule, blank,
     dot. If wrong, the fix is `task fmt`.
   - **English-only** — any Russian in comments, identifiers, log strings, or errors is a blocker.
   - **Logging level** — `warn`/`error` only for on-call-actionable events; routine flow is `debug`,
     not `info`.
   - **AC coverage** — every acceptance criterion in `spec.md` has corresponding code AND a
     table-driven testify test exercising it. Missing test for an AC is a blocker.

4. **Cross-check for drift.** spec → plan → tasks → code must agree:
   - Every AC in `spec.md` maps to a task in `tasks.md` and to a diff hunk.
   - Every file the diff touches is accounted for in `plan.md` (an unplanned cross-service edit is a
     blocker — flag it, AGENTS.md §8 "Ask first").
   - Every task marked done in `tasks.md` is actually present in the diff (no stubs, no `// ...`).
   - Anything in the code that is NOT in the spec/plan is scope creep — flag it.

5. **Verify the gate ran.** Confirm `task fmt` was applied, `task lint` and `task test` pass. If you
   can run them, do: `task lint && task test`. A red gate is a blocker.

## Output

List findings as `path/to/file.go:LINE — <problem> → <concrete fix>`, grouped **BLOCKER** then
**nit**. Example:
```
BLOCKER  internal/transport/grpc/handler.go:42 — handler calls h.repo.GetProduct directly
         → route through the service: h.svc.GetProduct(ctx, id)
BLOCKER  internal/repository/postgres/product.go:88 — returns partial domain.Product (Price, SKU zero)
         → fix the mapper to fill every field (AGENTS.md §5)
nit      internal/service/product.go:31 — log.Info on routine path → use log.Debug
```

If there are zero blockers, say so explicitly.

## Gate (restate before finishing)

Phase 7 is complete only when: the diff was read in full; every checklist item above was checked;
spec↔plan↔tasks↔code drift was cross-checked; and **every BLOCKER is fixed (re-run the diff to
confirm) before `/pr`.** Do not advance to `/pr` with an open blocker — fix it or ask.
