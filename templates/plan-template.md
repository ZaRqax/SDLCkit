<!-- Phase 3 artifact. Copy to specs/<TASK_ID>-<slug>/plan.md. Reads spec.md; describes HOW.
     Honor clean architecture (domain → repository → service → transport). Keep ≤ ~150 lines. -->

# Plan: <TASK_ID> — <short title>

- **Spec:** ./spec.md
- **Status:** DRAFT → APPROVED

## 1. Approach (1 paragraph)
<The chosen design in plain words, and why over the alternative(s).>

## 2. Architecture & layering
<Where each change lands across domain / repository / service / transport(grpc). Confirm transport
never calls a repository directly. New interfaces & domain types listed BEFORE their impls.>

## 3. Data model & migrations
<New/changed tables, columns, indexes. Migration name(s). SQLC queries to add (in db/queries/).
Remember: regenerate with `task sqlc`, never hand-edit sqlc/.>

## 4. Contracts (proto / gRPC / Kafka / GraphQL)
<New/changed proto messages & RPCs (contracts repo, `task gen`). Kafka topics & event shapes.
GraphQL schema changes (`task gqlgen`). Domain↔proto mapping notes.>

## 5. Affected files (verified to exist — grep/Serena, don't guess)
| File | Change |
|---|---|
| `internal/service/...go` | ... |
| `internal/transport/grpc/...go` | ... |

## 6. Test strategy
<Unit (testify suites, table-driven) per layer; integration; what mocks regenerate (`task mocks`).
Which ACs each test covers.>

## 7. Rollout / flags / risks
<Feature flag? Backward-compat? Migration order? On-call-relevant log lines (warn/error only).>

---
## Plan checklist
- [ ] Every AC in spec.md is addressed by something in this plan.
- [ ] Clean architecture preserved; no transport→repository shortcut.
- [ ] All affected files verified to exist.
- [ ] Codegen steps identified (sqlc / mocks / proto / gqlgen).
- [ ] Test strategy maps tests → ACs.
