---
name: serena-first
description: >
  Use whenever reading or editing Go code in this workspace. Prefer symbol-level
  navigation/editing over reading or rewriting whole files. Invoke with /serena-first
  for the full runbook.
---

# serena-first — symbol tools over whole-file reads/edits

**Default to Serena's symbol tools for all Go.** Reach for `read_file`/`Edit` only on
non-symbol files (yaml, sql, proto, markdown). This is mandatory, not a preference.

## Why
- **Token budget.** Reading a 600-line file to change one method burns context the model
  needs to reason. `find_symbol` returns just that method's body.
- **Edit reliability.** `replace_symbol_body` is anchored by the language server to the
  symbol — not by line numbers or fragile string matches that drift after a `task fmt`.
  Weak open models (GLM-5.1, Qwen3-Coder-Next) mis-apply whole-file rewrites; symbol edits
  are scoped and verifiable.

## Recipe — pick the tool by intent
- **Understand a file** → `get_symbols_overview` (the symbol map), then `find_symbol` on
  the one you care about. Do NOT `read_file` the whole file.
- **Assess blast radius before changing a symbol** → `find_referencing_symbols`. Every
  caller must still compile. If a public signature changes, this is your callsite list.
- **Edit** → `replace_symbol_body` (rewrite a function/method whole), `insert_after_symbol`
  / `insert_before_symbol` (add a new symbol next to an existing one), `rename_symbol`
  (rename + fix all references). Emit the COMPLETE body — never `// ... rest unchanged`.
- **Fall back to `read_file`/`Edit`** only for non-Go files Serena can't index: `db/queries/*.sql`,
  `db/migrations/*.sql`, `proto/*.proto`, `Taskfile.yml`, `*.yml`. (And never hand-edit generated
  Go under `sqlc/`, `mocks/`, `gen/` — change the source and rerun `task sqlc`/`mocks`/`gen`.)

## Worked sequence — add a `GetProduct` method to the service
1. **Overview** — map the file without reading it whole:
   `get_symbols_overview` on `internal/service/product.go`.
2. **Find** — pull just the target symbol:
   `find_symbol` name_path `Service`, `depth: 1` → see existing methods + signatures.
3. **Impact** — before touching `Service`, list callers:
   `find_referencing_symbols` for `Service` → confirms transport (not repo) calls it.
4. **Edit** — `insert_after_symbol` (anchor: the prior method) with the COMPLETE new method:
   ```go
   // GetProduct fetches a product by id via the repository.
   func (s *Service) GetProduct(ctx context.Context, id string) (domain.Product, error) {
       p, err := s.repo.GetProduct(ctx, id)
       if err != nil {
           return domain.Product{}, fmt.Errorf("get product %q: %w", id, err)
       }
       return p, nil
   }
   ```
5. **Verify** — `task fmt && task lint && task test`. Symbol edits keep gci import order and
   gofumpt formatting stable, so the diff is exactly your method.

## Prerequisite — gopls must index private modules
Serena drives `gopls`. Without access to private `github.com/acme` modules, `find_symbol`
returns empty for contracts/shared-lib types. Ensure the environment has:
```
export GOPRIVATE=github.com/acme
export GITHUB_PAT=<token-with-repo-read>   # gopls/go fetch private deps with this
```
If `find_symbol` comes back empty for a symbol you KNOW exists (e.g. a `catalogpb` message),
suspect a missing `GITHUB_PAT`/`GOPRIVATE` or an unbuilt module — fix the env, don't fall back
to blind whole-file reads.

**Reminder:** overview → find → reference-check → symbol-edit → verify. Whole-file reads/edits
are the exception (non-Go files only), never the default.
