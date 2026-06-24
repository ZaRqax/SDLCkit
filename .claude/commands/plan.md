---
description: Phase 3 (plan) — turn spec.md into a verified technical plan.md (architecture, data model, contracts, affected files, tests).
argument-hint: <TASK_ID>
allowed-tools: Read, Write, Edit, Grep, Glob, Bash
---

You are in **PHASE 3 — PLAN** of the pipeline `spec → clarify → plan → tasks → implement → test → review → pr`.
Say so first: announce "PHASE 3 (plan) for $1". You are designing HOW, not writing code yet.
The gate after this phase is `/tasks` (human approves before any code is written).

TASK_ID = `$1`. Work inside `specs/$1-<slug>/` (the slug already exists from the spec phase —
find it with `Glob: specs/$1-*/spec.md`).

## Steps (do them in order, do not skip)

1. **Read the spec.** Open `specs/$1-<slug>/spec.md` in full. Extract the acceptance criteria (ACs)
   into a list — every AC must be addressed by something in the plan. If `spec.md` is missing or has
   unresolved open questions, STOP and tell the human to run `/spec` and `/clarify` first.

2. **Verify reality with Serena before you write a single path or symbol.** Do not guess file names or
   APIs — confirm they exist. Use Serena symbol tools first (per AGENTS.md §6):
   - `get_symbols_overview` on the target service dir to see what's there.
   - `find_symbol` for each service/repository/handler you plan to touch (e.g. the `Service` struct,
     the `Repository` interface, the gRPC `Handler`).
   - `find_referencing_symbols` on any symbol you'll change, to size the blast radius.
   - Fall back to `Grep`/`Glob` only to locate proto messages, Kafka topics, SQLC queries, migrations.
   For any RPC/field/proto message you reference, confirm it in `gen/` or the contracts repo. If you
   cannot verify something exists, say so in the plan — never invent an API.

3. **Write `plan.md` from the template.** Read `templates/plan-template.md` and produce
   `specs/$1-<slug>/plan.md` filling every section with concrete, repo-specific content:
   - **Approach** — the chosen design in one paragraph, and why over the alternative.
   - **Architecture & layering** — where each change lands across `domain → repository → service →
     transport(grpc)`. Explicitly confirm **transport never calls a repository directly** (it goes
     through a service). List new interfaces and domain types BEFORE their implementations.
   - **Data model & migrations** — new/changed tables, columns, indexes; migration name(s)
     (`task db:migrate:create -- <name>`); SQLC queries to add under `db/queries/`. Note the codegen
     step: regenerate with `task sqlc`, never hand-edit `repository/postgres/sqlc/`.
   - **Contracts** — new/changed proto messages & RPCs (contracts repo, `task gen`), Kafka topics &
     event shapes, GraphQL schema (`task gqlgen`), and domain↔proto mapping notes. Honor NO partial
     structs: every mapper fills every field.
   - **Affected files** — a table of files you VERIFIED in step 2, each with the change. No guesses.
   - **Test strategy** — testify suites, table-driven, per layer; which mocks regenerate (`task mocks`);
     map each test to the AC(s) it covers (so step 6 `/test` can trace coverage).
   - **Rollout / flags / risks** — feature flag? backward-compat? migration order? warn/error log lines.

4. **List the codegen steps explicitly** in the plan: `task sqlc` (if SQL changed), `task mocks` (if an
   interface changed), contracts `task gen` (if proto changed), `task gqlgen` (GraphQL service only).
   Generated code is never hand-edited — it is regenerated.

## Before you finish — restate the plan checklist, ticked

- [ ] **Every AC in spec.md is addressed** by something in this plan — list AC → plan-section mapping.
- [ ] Clean architecture preserved; no transport→repository shortcut.
- [ ] No partial-struct mappers introduced (every field filled, or `optional.T[...]`).
- [ ] All affected files verified to exist via Serena/Grep — none invented.
- [ ] Codegen steps identified (sqlc / mocks / gen / gqlgen).
- [ ] Test strategy maps tests → ACs.

If any AC is unaddressed or any path is unverified, fix it before reporting done — do not claim success.

**Next:** hand off to `/tasks $1` to break this plan into small, ordered, AC-traceable tasks for human approval.
