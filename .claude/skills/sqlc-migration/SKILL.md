---
name: sqlc-migration
description: >
  Use when changing the database schema or adding a query: create a golang-migrate migration,
  add SQL to db/queries/, regenerate sqlc — never hand-edit generated code. Invoke with
  /sqlc-migration for the full runbook.
---

> Optional Go profile capability. Apply only when the target repository uses this stack/toolchain; nearest project instructions and effective policy determine commands, architecture and authorization. This runbook is not a default dependency of generic workflows.

# sqlc-migration

Add or change a Postgres table/query the safe way: migration → query SQL → regenerate → wire through
the repository interface and service. **Generated code (`internal/repository/postgres/sqlc/`) is the
source of truth for signatures — never hand-edit it. Edit the SQL and rerun `task sqlc`.**

This is also a `db:migrate` change → it is in the **Ask first** boundary. Confirm with the human
before running migrations, and announce the **implement** phase.

## Runbook

### 1. Create the migration (ask first)
```bash
task db:migrate:create -- add_product_sku
# → db/migrations/000042_add_product_sku.up.sql
# → db/migrations/000042_add_product_sku.down.sql
```

### 2. Write up + down SQL (both halves — down must fully reverse up)
```sql
-- 000042_add_product_sku.up.sql
ALTER TABLE products ADD COLUMN sku TEXT NOT NULL DEFAULT '';

-- 000042_add_product_sku.down.sql
ALTER TABLE products DROP COLUMN sku;
```
Apply it: `task db:migrate:up`. sqlc reads the migrations as its schema source, so the schema must
migrate cleanly before you regenerate.

### 3. Add the query to `db/queries/*.sql` with sqlc annotations
The annotation name becomes the generated Go method; `:one`/`:many`/`:exec` picks the return shape.
```sql
-- name: GetProductBySKU :one
SELECT id, name, price, sku, created_at
FROM products
WHERE sku = $1;
```

### 4. Regenerate
```bash
task sqlc
```
This writes `internal/repository/postgres/sqlc/` (the `Queries` struct + `GetProductBySKU`). **Do not
open or edit those files.** If the signature is wrong, fix the SQL and rerun `task sqlc`.

### 5. Wire it through — interface FIRST, then service (clean architecture)
Define the repository interface method before touching the impl. Transport never calls this directly —
it goes through the service. Edit these Go files with Serena symbol tools (insert_after_symbol /
replace_symbol_body), not whole-file rewrites.
```go
// internal/repository/repository.go — interface defined here, BEFORE the impl
type Repository interface {
    GetProductBySKU(ctx context.Context, sku string) (domain.Product, error)
}

// internal/repository/postgres/product.go — adapter over generated code; full struct, no zero-fill
func (r *PostgresRepository) GetProductBySKU(ctx context.Context, sku string) (domain.Product, error) {
    row, err := r.q.GetProductBySKU(ctx, sku) // r.q is *sqlc.Queries — generated
    if err != nil {
        return domain.Product{}, fmt.Errorf("get product by sku %q: %w", sku, err)
    }
    return domain.Product{
        ID:        row.ID,
        Name:      row.Name,
        Price:     row.Price,
        SKU:       row.Sku,
        CreatedAt: row.CreatedAt,
    }, nil // every field set — NO partial struct (§5)
}

// internal/service/product.go — business logic calls the repo interface
func (s *Service) GetProductBySKU(ctx context.Context, sku string) (domain.Product, error) {
    return s.repo.GetProductBySKU(ctx, sku)
}
```

### 6. Regenerate mocks + verify
The interface changed, so mocks are stale:
```bash
task mocks   # regenerates internal/repository/mocks/ — also never hand-edited
task lint
task test
```

## Hard rules
- **Never edit `internal/repository/postgres/sqlc/` or `internal/repository/mocks/` by hand.** Change
  the SQL / interface, then `task sqlc` / `task mocks`. Both go INTO the `feat`/`fix` commit.
- Write **both** up and down SQL; the down must reverse the up exactly.
- Map generated rows into **fully-populated** domain structs — no zero-filled fields.
- All SQL comments and migration names in **English**.
- Migrations are **Ask first** — confirm before `task db:migrate:*`.
