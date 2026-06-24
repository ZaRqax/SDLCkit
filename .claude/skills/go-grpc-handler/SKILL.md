---
name: go-grpc-handler
description: >
  Use when adding or changing a gRPC RPC: wire the transport handler, the service method, and
  the repository call, with proto<->domain mapping. Invoke with /go-grpc-handler for the full
  reference (mapping patterns, full error-code table, streaming notes).
---

# go-grpc-handler — wire an RPC end to end

Scope: a single RPC flows `transport(grpc) → service → repository`, one direction only.
**Transport NEVER touches a repository.** Define the domain type and repository interface
before their implementations. Read AGENTS.md §3–§5 first.

## Runbook

1. **Proto first (contracts repo).** The RPC/message lives in `contracts-proto/proto/`.
   Edit the `.proto`, then regenerate — never hand-edit `gen/`:
   ```bash
   cd contracts-proto && task gen   # Buf → gen/gen/...
   ```
   In the service, bump the contracts module if needed: `go get github.com/acme/contracts-go@latest`.
2. **Verify the generated signature** before you call it. Use Serena `get_symbols_overview` on the
   generated package, or grep — do not invent message/field names.
3. **Domain + repository interface** (define before impl). Confirm `service.X` and the repo method
   exist with `find_symbol`; add them if missing.
4. **Service method** — orchestrates, calls the repository interface, returns a domain value or a
   domain error. No proto types in the service layer.
5. **Handler** — map proto→args, delegate to the service, map domain→proto, map domain error→gRPC status.
6. **Mapper** — pure proto↔domain functions in `transport/grpc/`. Fill **every** field (no partial structs, §5).
7. **Test** — table-driven testify with a mock repository (`task mocks` if the interface changed).
8. **Run the gates**: `task fmt && task lint && task test`. Smoke-test with grpcurl (below).

## Worked example — `GetProduct`

`internal/transport/grpc/handler.go` — delegates to the service, never the repository:
```go
func (h *Handler) GetProduct(ctx context.Context, req *catalogpb.GetProductRequest) (*catalogpb.GetProductResponse, error) {
    p, err := h.svc.GetProduct(ctx, req.GetId()) // service, never repo
    if err != nil {
        return nil, mapDomainErr(err) // domain error → gRPC status
    }
    return &catalogpb.GetProductResponse{Product: toProtoProduct(p)}, nil
}
```

`internal/transport/grpc/mapper.go` — pure mapping, every field set:
```go
func toProtoProduct(p domain.Product) *catalogpb.Product {
    return &catalogpb.Product{
        Id:        p.ID,
        Name:      p.Name,
        Sku:       p.SKU,
        Price:     p.Price.String(),
        CreatedAt: timestamppb.New(p.CreatedAt),
    }
}
```

`internal/service/product.go` — calls the repository interface, returns domain values/errors:
```go
func (s *Service) GetProduct(ctx context.Context, id string) (domain.Product, error) {
    if id == "" {
        return domain.Product{}, domain.ErrInvalidArgument
    }
    p, err := s.repo.GetProduct(ctx, id) // repository interface
    if err != nil {
        return domain.Product{}, fmt.Errorf("get product %q: %w", id, err)
    }
    return p, nil
}
```

`internal/repository/product.go` — interface defined in the repository layer (impl in `postgres/`):
```go
type Repository interface {
    GetProduct(ctx context.Context, id string) (domain.Product, error)
}
```

## Domain error → gRPC status (in `mapDomainErr`)

| Domain error | gRPC code |
|---|---|
| `domain.ErrNotFound` | `codes.NotFound` |
| `domain.ErrInvalidArgument` | `codes.InvalidArgument` |
| `domain.ErrAlreadyExists` | `codes.AlreadyExists` |
| `domain.ErrPermission` | `codes.PermissionDenied` |
| anything else | `codes.Internal` (log it; do not leak internals) |

```go
func mapDomainErr(err error) error {
    switch {
    case errors.Is(err, domain.ErrNotFound):
        return status.Error(codes.NotFound, err.Error())
    case errors.Is(err, domain.ErrInvalidArgument):
        return status.Error(codes.InvalidArgument, err.Error())
    default:
        return status.Error(codes.Internal, "internal error")
    }
}
```

## grpcurl smoke test

```bash
grpcurl -plaintext -d '{"id":"p1"}' localhost:50051 catalog.v1.CatalogService/GetProduct
```
Expect the populated `product` for a known id, and a `NotFound` status for a missing one.

## Definition of Done (restate, ticked)
- [ ] Proto edited in contracts repo + `task gen`; generated code not hand-edited.
- [ ] Handler delegates to the service, never the repository (§3).
- [ ] Mapper sets every field — no partial structs (§5).
- [ ] Domain errors mapped to gRPC status codes per the table.
- [ ] Table-driven test with mock repo; `task fmt`/`task lint`/`task test` green; grpcurl smoke passes.
