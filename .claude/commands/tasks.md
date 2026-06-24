---
description: Phase 4 (tasks) — turn plan.md into a small, ordered, AC-traceable tasks.md, then STOP for human approval.
argument-hint: <TASK_ID>
allowed-tools: Read, Write, Glob, Grep
---

You are in the **TASKS** phase (phase 4 of `spec → clarify → plan → tasks → implement → test → review → pr`).
Announce this first: "Phase 4 — TASKS for $1." Do **not** write any code in this phase. Your single
deliverable is `tasks.md`, and you must STOP for human approval before phase 5.

## 1. Locate the spec folder and read the plan
- Find the folder: `specs/$1-*/` (Glob `specs/$1-*/plan.md`). If there are two, pick the exact `$1` match.
- If `plan.md` does not exist, STOP and say: "No plan.md for $1 — run /plan first." Do not invent a plan.
- Read in full: `plan.md` (architecture, data model, contracts, affected files) and `spec.md` (the
  acceptance criteria — AC-1, AC-2, …). You will trace every task back to an AC.

## 2. Decompose into small, ordered, traceable tasks
Open `templates/tasks-template.md` and follow its shape exactly. Rules for the task list:
- **Small & single-purpose.** One logical change per task (smallest change that satisfies it). If a
  task would touch >1 service, split it and flag the boundary — that needs human sign-off later.
- **Ordered & dependency-aware.** Domain/interface tasks BEFORE their impls (clean architecture:
  `domain → repository → service → transport`). State "depends on Tn" where real.
- **`[P]` only when truly independent** — two `[P]` tasks at the same step touch disjoint files and
  share no ordering. When unsure, do NOT mark `[P]`.
- **AC traceability is mandatory.** Every task names the AC(s) it covers (`covers AC-2`); every AC in
  spec.md is covered by at least one task. Always include a final task: `task fmt && task lint &&
  task test` green = the Definition of Done gate.
- **Verify file paths and symbols before listing them** (Glob/Grep, or Serena `find_symbol` in
  implement). Do not name a file or symbol you have not confirmed exists. If you cannot verify, say so.

## 3. Write one self-contained story block per task
Each task gets its own block so the implementer (a weaker model) needs nothing else open. Pack:
- **Goal** (one sentence), **AC covered**, **Files to touch (verified)**, **Relevant existing symbols**
  (note "confirm with Serena find_symbol"), **Constraints**, **Done when**, **Notes/gotchas**.
- Bake the team rules into Constraints where they bite: no partial structs (fill every `domain.X{...}`
  field or use `optional.T[...]`); transport never calls a repository; English-only code; if an
  interface/SQL/proto changes, regenerate (`task mocks` / `task sqlc` / contracts `task gen`) — never
  hand-edit `mocks/`, `sqlc/`, or `gen/`; tests are testify table-driven (AAA), errors wrap with `%w`.

Example of one well-formed task block (adapt to the real plan — don't copy literally):
```
### T2 — Add GetProduct to the catalog service
- **Goal:** service.GetProduct fetches a product by id via the repository and maps errors.
- **AC covered:** AC-1
- **Files to touch (verified):** internal/service/product.go, internal/service/product_test.go
- **Relevant existing symbols:** service.Service, repository.ProductStore (confirm: Serena find_symbol)
- **Constraints:** transport→service→repository (no repo call from transport); no partial domain.Product
  literal; wrap errors `fmt.Errorf("get product %q: %w", id, err)`; English-only.
- **Done when:** AC-1 behavior observable and its testify table-driven test passes.
- **Notes / gotchas:** if repository.ProductStore gains a method, run `task mocks` (don't edit mocks/).
```

## 4. Write the file, then STOP
- Write `specs/$1-<slug>/tasks.md` from the template (use the same `<slug>` as the folder). Set
  **Status: DRAFT**. Emit the COMPLETE file — no `// ...`, no "rest unchanged".
- End your message by restating the gate: "Phase 4 gate — human must APPROVE tasks.md before any code
  is written (phase 5 /implement). Review the task list, [P] markers, and AC coverage above."
- Do not start implementing. Do not change Status past DRAFT yourself — the human flips it to APPROVED.

**Gate:** human approves `tasks.md`. Until then, the TASKS phase is not complete.
