---
description: Phase 5 — implement the approved tasks one at a time with Serena symbol edits.
argument-hint: <TASK_ID>
allowed-tools: Read, Edit, Write, Bash, Grep, Glob
---

You are in the **IMPLEMENT** phase (phase 5 of `spec → clarify → plan → tasks → implement → test → review → pr`).
State that out loud, then execute. TASK_ID = `$1`.

Goal: turn the **approved** `tasks.md` into working code — **one task at a time**, smallest correct
change per task, Serena symbol edits over whole-file rewrites. You do not write tests-green here; that
is `/test`. You do write the code each task asks for, and tick it off.

## Preconditions
1. Read `specs/$1-*/tasks.md`. If its **Status** is not `APPROVED` (or `IN_PROGRESS`), stop and ask the
   human to approve it — do not code against a DRAFT.
2. Read `specs/$1-*/plan.md` for architecture/data-model/contracts context. Don't re-read whole source files yet.
3. Confirm you are on branch `feature/$1-<desc>` (or `fix/$1-...`). If on `develop`/`main`, stop and ask.

## Per-task loop (repeat in order; respect dependencies; `[P]` tasks may be done together)
For each unchecked task `Tn`:

1. **Read its story block** in `tasks.md` — Goal, AC covered, Files to touch, Relevant existing symbols,
   Constraints, Done-when. That block is your brief; do exactly it, nothing more.

2. **Locate symbols with Serena — do NOT read whole files.**
   - `get_symbols_overview` on each file the story lists, then `find_symbol` for the exact target.
   - `find_referencing_symbols` before changing any symbol others call, to size the blast radius.
   - **Verify every symbol the story names actually exists.** If a named symbol/field/proto message is
     missing or has a different signature, STOP — fix the story or ask. Never invent an API (DoD §9).

3. **Make the smallest change with Serena symbol edits** (`replace_symbol_body`, `insert_after_symbol`,
   `insert_before_symbol`, `rename_symbol`) — anchored by the language server, not line numbers.
   Read the symbol before you edit it. One logical change at a time; no opportunistic refactors/renames.
   - **Clean architecture:** `domain → repository → service → transport`. Transport must NEVER call a
     repository — go through a service:
     ```go
     // transport/grpc/handler.go — delegate to the service, then map back. No repo access here.
     func (h *Handler) GetProduct(ctx context.Context, req *catalogpb.GetProductRequest) (*catalogpb.GetProductResponse, error) {
         p, err := h.svc.GetProduct(ctx, req.GetId()) // service, never repo
         if err != nil {
             return nil, mapDomainErr(err)
         }
         return &catalogpb.GetProductResponse{Product: toProto(p)}, nil
     }
     ```
   - **NO partial structs.** Never zero-fill a domain literal to make it compile — fill every field, fix
     the source mapper/SQL, or make the field `optional.T[...]` if absence is a real business case:
     ```go
     // ❌ return domain.Product{ID: id, Name: name}            // Price, SKU silently zero
     return domain.Product{ID: id, Name: name, Price: price, SKU: sku, CreatedAt: createdAt} // ✅
     ```
   - Errors wrapped with `%w`, lowercase, no trailing punctuation:
     `return fmt.Errorf("get product %q: %w", id, err)`. English only in code/comments/logs.
     gci import order, gofumpt, ≤130 cols. Logging defaults to `debug`.
   - Define interfaces/domain types BEFORE their implementations.

4. **Regenerate codegen if you changed its inputs — never hand-edit generated output.**
   - Changed a `.sql` query → `task sqlc`. Changed an interface → `task mocks`. Changed proto (contracts
     repo) → `task gen`. Editing `repository/postgres/sqlc/`, `mocks/`, or `gen/` by hand is forbidden.

5. **Tick the task** in `tasks.md` (`- [ ]` → `- [x]`) and set Status to `IN_PROGRESS`. This file is your
   external memory — update it after every task, not from memory.

## Reminders
- One logical change at a time. Read-before-edit, verify-before-claim. Serena symbol tools first.
- If a task is ambiguous, or a change unexpectedly crosses a service boundary, STOP and ask one question.
- Commits (when asked): `feat($1): <desc>` / `fix($1): <desc>`; codegen regen goes INTO that commit, not a `chore`.

## Gate
You have NOT finished phase 5 until every task in `tasks.md` is `[x]`, no stub/TODO/elision, no partial
struct, no hand-edited generated code. The code need not be lint/test-green yet — that is the next phase.
If you can't complete a task, say which and why, and ask. Then hand off: **run `/test`.**
