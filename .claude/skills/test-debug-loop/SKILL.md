---
name: test-debug-loop
description: >
  Use to reproduce, isolate, fix, and validate a failing Go test or runtime failure in this
  workspace — when `task test` is red, a suite flakes, or a service panics. One hypothesis at a
  time; never shotgun-edit. Invoke with /test-debug-loop for the full reference.
---

# test-debug-loop — reproduce → isolate → fix → validate

Standalone runbook for phase 6 (test) when something is broken. You are debugging a failing test or
runtime error in a Acme Go service. Work the loop in order; change **one thing per iteration** and
re-run the exact failing command. If you cannot fix it after 2–3 honest hypotheses, **stop and ask** —
do not thrash (AGENTS.md §0.6).

## Steps

1. **Capture the exact failure.** Copy the failing command and the precise error/stack — not a
   paraphrase. The command is almost always `RUN=<TestOrSuiteName> task test`.
2. **Reproduce locally, narrowed.** Re-run just the failing test: `RUN=TestProductServiceSuite task test`.
   Confirm it fails the same way every run. If it only sometimes fails, it is a **flake** — keep the
   race detector on (`task test` already passes `-race`) and suspect shared state / goroutines / time.
3. **Isolate with Serena, don't read whole files.** `find_symbol` the method under test and the symbol
   in the stack trace; `find_referencing_symbols` to see callers. Form **one** hypothesis about the
   root cause and write it down.
4. **Patch the cause, minimally.** Edit via Serena symbol tools. If the cause is in generated code,
   the input is wrong — fix the SQL/proto/interface and regenerate (`task sqlc`/`mocks`/`gen`), never
   hand-edit `sqlc/`,`mocks/`,`gen/`.
5. **Re-run the failing command.** If still red, revert the change and try the next hypothesis — never
   stack speculative edits.
6. **Run adjacent tests + lint.** Once green: `task test` (whole package, race on) + `task lint` to
   confirm you didn't break a neighbor or introduce a partial struct / lint violation.
7. **Record what you learned.** Append a one-line Log entry to `specs/<TASK_ID>-<slug>/handoff.md`
   (root cause + fix). For a long hunt, keep a running `specs/<TASK_ID>-<slug>/debug.md` of
   hypotheses tried and ruled out, so the next session doesn't repeat them.

## Worked example

`RUN=TestProductServiceSuite task test` fails:

```
--- FAIL: TestProductServiceSuite/TestGetProduct/propagates_repository_error
    product_test.go:97: Error "get product \"missing\": not found" does not match expected nil
```

- **Hypothesis 1:** the service swallows the repo error. `find_symbol GetProduct` (service) shows it
  wraps with `%w` and returns — so the path is correct; the *test* expectation is the suspect.
- **Look again:** the failing row set `wantErr: true` but also a non-zero `want`; the assert checks
  `want` before returning on error. Root cause is the **test**, not the code.
- **Fix (one change):** in that row, drop the `want` value and keep `wantErr: true`; the `s.Require().
  Error(err); return` branch already covers it.
- **Re-run:** `RUN=TestProductServiceSuite task test` → green. Then `task test` + `task lint` → green.
- **Record:** handoff Log → "fixed false-fail in TestGetProduct error row (asserted want on error path)".

## Rules

- **One hypothesis, one change, re-run.** No batching speculative fixes; you won't know which worked.
- **Reproduce before you fix.** A fix you can't tie to a reproduced failure is a guess.
- **Flake ≠ bug-in-your-diff, but treat it as real.** Race-detector failures and order-dependent
  passes are bugs — fix the shared state, don't `-count=1` them away.
- **Don't weaken the test to make it pass.** Changing an assertion is only valid when the *test* was
  wrong (as above); never delete a case or loosen an assert just to go green.
- **Generated code is never the fix site.** Regenerate from its source instead.
- **Stuck after 2–3 tries → ask** with the captured error and what you ruled out. English only.
