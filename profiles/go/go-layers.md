---
description: Clean-architecture layering rules for Go service code; loads when touching internal/**
paths:
  - "**/internal/**/*.go"
  - "**/cmd/**/*.go"
---

# Go layering rules (loaded only when editing Go service files)

The dependency direction is one-way: **domain → repository → service → transport(grpc)**.

- **`internal/domain/`** — pure entities. No imports of repository/service/transport, no gRPC, no SQL.
- **`internal/repository/`** — interfaces live here; Postgres impl under `repository/postgres/`
  (SQLC-generated under `repository/postgres/sqlc/` — never hand-edit), mocks under `repository/mocks/`.
- **`internal/service/`** — orchestration + business rules; the only layer that calls repositories;
  publishes Kafka events here.
- **`internal/transport/grpc/`** — handlers + proto↔domain mappers. **Never** import or call a
  repository. Always go through a service.

Checklist when you touch this layer:
- [ ] Did transport call only services (not repositories)?
- [ ] Did you define the interface/domain type before its implementation?
- [ ] Did you avoid a partial `domain.X{}` literal (fill all fields or use `optional.T[...]`)?
- [ ] If you changed an interface or SQL, did you regenerate (`task mocks` / `task sqlc`) instead of
      editing generated files?
- [ ] Factory pattern preserved for product-type-specific repository behavior?
