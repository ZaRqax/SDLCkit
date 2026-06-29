---
description: Phase 7 (review) — review the diff against the kit checklist and cross-check spec↔plan↔tasks↔code for drift.
argument-hint: <TASK_ID>
---

You are in **PHASE 7 — review** for **$1**. The gate (AGENTS.md §9 Definition of Done): **every
blocker you find must be fixed before `/pr`.** Review notes are an artifact, not the goal — a clean
diff is.

**Claude only:** delegate this entire phase to the **go-code-reviewer** subagent (pass `$1` and the
spec dir); it runs the multi-pass review below. Open agents: run the steps yourself.

## Discipline (apply throughout)
- **Read-only** — never edit, never run codegen, never commit.
- **Verify before you flag** — grep/Read/Serena to confirm an API/field exists before calling it
  wrong. A suspicion you can't confirm is a *question*, not a blocker.
- **Bounded context** — read the enclosing function/type (Serena `find_symbol`), never judge a line
  in isolation.
- **Score each finding** `severity` ∈ {blocker, major, minor, nit} + `confidence` ∈ {high, medium,
  low}; name the rule it breaks. **Self-refute** each one before writing it down — drop anything you
  can't defend at ≥ medium confidence. Don't inflate nits; don't bury blockers.

## Workflow

1. **Locate artifacts.** `ls specs/$1-*/` → read `spec.md` (acceptance criteria AC-1…AC-N), `plan.md`
   (intended files/contracts), `tasks.md` (checklist). They are the contract you review against.

2. **Get the diff.** Run it; read every hunk (not just `--stat`).
   ```bash
   git fetch origin develop -q
   git diff --merge-base origin/develop --stat
   git diff --merge-base origin/develop
   ```

3. **Review, pass by pass:**
   - **Correctness & bugs** — nil/zero, type-assert without `,ok`, swallowed/wrong-wrapped errors,
     logic vs the AC, data races / goroutine leaks / loop-var capture, missing `defer Close`, `ctx`
     not propagated, N+1 / missing tx / `UPDATE` without `WHERE`, unhandled `sql.ErrNoRows`.
   - **Architecture & principles** — clean arch: transport must NEVER call a repository (§3, a
     `h.repo.Get` instead of `h.svc.Get` is a blocker); SOLID (SRP/OCP/LSP/ISP/DIP); DRY (real
     duplication, not coincidental); KISS/YAGNI (flag speculative abstractions, unused params, one-
     impl interfaces, dead flags).
   - **Go idioms** — `%w` + lowercase context, no trailing punctuation; `ctx` first param, never
     `context.Background()` on a request path; accept interfaces / return structs; no `panic` in
     service code; gci import order + gofumpt + ≤130 cols (these are nits, `task fmt` fixes them).
   - **Security** — SQL string-concatenation (injection), unvalidated boundary input, secrets/PII in
     logs or error messages, missing authz on a mutating RPC, unbounded input.
   - **Tests** — every AC has a table-driven testify test (race on) asserting behavior not internals;
     no test weakened/skipped to pass; mocks regenerated not hand-edited; no partial-struct asserts.
     A missing test for an AC is a **blocker**.
   - **Project rules (Acme house rules — each a blocker):**
     - No partial `domain.X{...}` literal (§5) — fill every field / fix the mapper/SQL / `optional.T`.
       ```go
       return domain.Product{ID: id, Name: name}   // ❌ Price, SKU silently zero — blocker
       ```
     - Interfaces defined at the **consumer**, before the implementation; small + client-shaped.
     - Mappers (proto↔domain in transport, row↔domain in repo) are total & dumb: every field mapped,
       no business logic, no silent drops. A forgotten field = the partial-struct bug → blocker.
     - Generated code (`sqlc/`, `mocks/`, `gen/`, `*.pb.go`) never hand-edited → regenerate.
     - Logging `debug`-default; `warn`/`error` only on-call-actionable. English-only in code.

4. **Cross-check for drift.** spec → plan → tasks → code must agree: every AC maps to a task and a
   hunk; every done task is really in the diff (no `// ...` stubs); every touched file is in `plan.md`
   (unplanned cross-service edit = blocker); plan contracts (proto/methods) actually exist — grep to
   confirm, flag hallucinated/renamed APIs. Anything in the code not in the spec/plan is scope creep.

5. **Verify the gate ran.** `task fmt` applied, `task lint` + `task test` pass. If you can run them,
   do: `task lint && task test`. A red gate is a blocker.

## Output

Group findings by severity (blockers first):
```
[blocker · high]  internal/transport/grpc/handler.go:42
    rule: clean architecture (§3) — handler calls h.repo.GetProduct directly
    fix:  route through the service: h.svc.GetProduct(ctx, id)
[major · medium]  internal/repository/postgres/product.go:88
    rule: §5 — returns partial domain.Product (Price, SKU zero)
    fix:  fill every field in the mapper
```
End with: `reviewed N files, M hunks · b blocker / mj major / mn minor / n nit · suppressed s` and a
`VERDICT: PASS` or `VERDICT: BOUNCE — b blocker(s) → engineer (phase 5)`. If zero blockers, say so.

## Gate (restate before finishing)

Phase 7 is complete only when: the diff was read in full; every pass above was run; spec↔plan↔tasks↔code
drift was cross-checked; and **every blocker is fixed (re-run the diff to confirm) before `/pr`.** Do
not advance to `/pr` with an open blocker — fix it or ask.
