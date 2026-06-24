<!-- Per-service nested AGENTS.md template. The kit's root AGENTS.md holds the workspace-wide rules;
     drop a filled copy of THIS file at the root of an individual service repo (e.g.
     catalog/AGENTS.md) to add service-specific detail. Agents read the NEAREST
     AGENTS.md to the file they're editing, so keep this short — only what differs from the root. -->

# AGENTS.md — <Service name> (e.g. Catalog)

Inherits all workspace rules from the root `AGENTS.md`. Service-specific notes:

## This service in one line
<What it owns, e.g. "Products, categories, documents, assemblies." Its gRPC + Kafka surface.>

## Commands (anything that differs from the root)
- DB: `task db:migrate:up` against database `<db-name>` on Postgres `:15000`.
- Local run: `task run` (or `task docker:go`), gRPC on `:50051`.
- Codegen this service uses: `task sqlc` <and/or `task gqlgen` / proto via contracts `task gen`>.

## Domain & layout notes
- Key domains: `<list the main domain types>`.
- Repository factory: `<note any product-type-specific factory behavior>`.
- Kafka topics produced/consumed: `<topic names>`.
- External integrations: `<e.g. OpenSearch index, Redis cache, S3>`.

## Gotchas specific to this service
- <e.g. "Offer pricing must go through the pricing service, never recomputed in transport.">
- <e.g. "Inventory sync events are idempotent on (offerID, version) — preserve that.">
