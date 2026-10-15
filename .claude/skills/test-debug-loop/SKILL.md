---
name: test-debug-loop
description: Reproduce, isolate and fix a failing check
---

# test-debug-loop

Capture the exact failing command, working directory, exit status and error/stack. Reproduce the smallest relevant case using the target project's actual runner. Inspect the implicated code and callers with available search/LSP/file tools. Form one evidence-backed hypothesis, patch the cause minimally and rerun the failing command.

Do not stack speculative edits, weaken assertions or hand-edit generated outputs. For nondeterministic failures inspect shared state, time/resources and concurrency with the project's tools. Once the root cause is fixed run adjacent relevant tests and required lint/build checks. Record the hypothesis, fix and observed evidence in the task/handoff. If progress requires missing product decisions or external authority, ask one concrete question with evidence.

Example: a Python test fails only when executed after another test. Reproduce both in order, inspect leaked shared fixtures, isolate fixture state and rerun the failing pair plus the relevant suite. A command that cannot run is unavailable, not successful.
