# go-grpc-handler — reference

Longer detail behind the SKILL.md runbook. Read SKILL.md first; this expands mapping,
error codes, and streaming. Conventions from AGENTS.md still bind (§3 clean architecture,
§5 no partial structs, §6 generated code never hand-edited, §7 commits/branches).

## Layer boundaries (recap)

```
domain  →  repository  →  service  →  transport(grpc)
```
- **domain** — pure entities + sentinel errors. No proto, no pgx, no grpc imports.
- **repository** — interface here; impl in `repository/postgres/` (SQLC). Returns domain types.
- **service** — orchestration + Kafka events. Returns domain values and domain errors. No proto types.
- **transport/grpc** — handlers + proto↔domain mappers. The ONLY place proto types appear.

Transport calling a repository directly is a hard violation. If a handler needs data, add/extend a
service method.

## Full proto ↔ domain mapping patterns

Keep mappers pure (no I/O), in `transport/grpc/mapper.go`, one direction per function. Fill every
field — a zero-filled domain struct is the team's #1 recurring bug (§5).

**Scalars + decimals.** Money/decimals cross the wire as strings; parse on the way in, format on the
way out:
```go
func fromProtoProduct(p *catalogpb.Product) (domain.Product, error) {
    price, err := decimal.NewFromString(p.GetPrice())
    if err != nil {
        return domain.Product{}, fmt.Errorf("parse price %q: %w", p.GetPrice(), err)
    }
    return domain.Product{
        ID:        p.GetId(),
        Name:      p.GetName(),
        SKU:       p.GetSku(),
        Price:     price,
        CreatedAt: p.GetCreatedAt().AsTime(),
    }, nil
}
```

**Timestamps.** `timestamppb.New(t)` out; `ts.AsTime()` in. Guard nil if the field is optional in proto.

**Enums.** Map explicitly both ways; never rely on integer equality across proto/domain:
```go
func toProtoStatus(s domain.Status) catalogpb.Status {
    switch s {
    case domain.StatusActive:
        return catalogpb.Status_STATUS_ACTIVE
    case domain.StatusArchived:
        return catalogpb.Status_STATUS_ARCHIVED
    default:
        return catalogpb.Status_STATUS_UNSPECIFIED
    }
}
```

**Repeated / nested.** Map element-by-element through the element mapper; preallocate:
```go
func toProtoProducts(ps []domain.Product) []*catalogpb.Product {
    out := make([]*catalogpb.Product, 0, len(ps))
    for _, p := range ps {
        out = append(out, toProtoProduct(p))
    }
    return out
}
```

**Optional / sometimes-absent fields.** Use `optional.T[...]` in the domain, and proto `optional`
scalars. Do not zero-fill to dodge absence:
```go
if v, ok := p.Description.Get(); ok {
    out.Description = proto.String(v)
}
```

**Pagination.** Carry page/size/cursor through a domain filter struct; the service applies it, the
repository translates it to SQL (`LIMIT/OFFSET` or keyset). Return total count in the response message.

## Domain error → gRPC status (full table)

Define sentinels in `domain/errors.go`; match with `errors.Is`. Default to `Internal` and log the raw
error at `error` level (an on-call engineer must act) — never leak internals to the client.

| Domain sentinel | gRPC code | When |
|---|---|---|
| `domain.ErrNotFound` | `codes.NotFound` | row/aggregate absent |
| `domain.ErrInvalidArgument` | `codes.InvalidArgument` | bad/empty input, parse failure |
| `domain.ErrAlreadyExists` | `codes.AlreadyExists` | unique-constraint / duplicate create |
| `domain.ErrConflict` | `codes.FailedPrecondition` | stale version / state precondition |
| `domain.ErrPermission` | `codes.PermissionDenied` | caller lacks rights |
| `domain.ErrUnauthenticated` | `codes.Unauthenticated` | missing/invalid identity |
| `context.DeadlineExceeded` | `codes.DeadlineExceeded` | upstream timeout |
| `context.Canceled` | `codes.Canceled` | caller cancelled |
| anything else | `codes.Internal` | unexpected; log it |

```go
func mapDomainErr(err error) error {
    switch {
    case errors.Is(err, domain.ErrNotFound):
        return status.Error(codes.NotFound, err.Error())
    case errors.Is(err, domain.ErrInvalidArgument):
        return status.Error(codes.InvalidArgument, err.Error())
    case errors.Is(err, domain.ErrAlreadyExists):
        return status.Error(codes.AlreadyExists, err.Error())
    case errors.Is(err, domain.ErrConflict):
        return status.Error(codes.FailedPrecondition, err.Error())
    case errors.Is(err, domain.ErrPermission):
        return status.Error(codes.PermissionDenied, err.Error())
    case errors.Is(err, domain.ErrUnauthenticated):
        return status.Error(codes.Unauthenticated, err.Error())
    case errors.Is(err, context.DeadlineExceeded):
        return status.Error(codes.DeadlineExceeded, err.Error())
    case errors.Is(err, context.Canceled):
        return status.Error(codes.Canceled, err.Error())
    default:
        log.Error().Err(err).Msg("unhandled domain error")
        return status.Error(codes.Internal, "internal error")
    }
}
```

## Codegen (never hand-edit `gen/`)

1. Edit the `.proto` in `contracts-proto/proto/`.
2. `task gen` (Buf v2) → code in `gen/gen/`, published as
   `github.com/acme/contracts-go`.
3. In the consuming service: `go get github.com/acme/contracts-go@latest && go mod tidy`.
4. If the repository interface changed: `task mocks`. If SQL changed: `task sqlc`.
   These regen outputs go INTO the `feat`/`fix` commit, never a separate `chore` (§7).

## Streaming RPCs

**Server-streaming** — handler receives the stream, the service yields via a callback or channel; the
handler maps each item and calls `stream.Send`. Keep proto out of the service: pass a
`func(domain.Product) error` sink, or return a channel the handler drains.
```go
func (h *Handler) ListProducts(req *catalogpb.ListProductsRequest, stream catalogpb.CatalogService_ListProductsServer) error {
    return h.svc.ListProducts(stream.Context(), fromProtoFilter(req), func(p domain.Product) error {
        return stream.Send(toProtoProduct(p)) // map per item
    })
}
```
- Respect `stream.Context()` cancellation; stop work when it's done.
- Channels size 0 or 1 unless a buffer is justified (senior Go goroutine discipline).
- Errors still go through `mapDomainErr`; return it from the handler (the stream closes with that status).

**Client-streaming / bidi** — same boundary rule: the handler owns `Recv`/`Send` and mapping; the
service works in domain types only. Validate each received message before handing it to the service.

## grpcurl recipes

```bash
# list services / methods (reflection must be enabled on the server)
grpcurl -plaintext localhost:50051 list
grpcurl -plaintext localhost:50051 list catalog.v1.CatalogService

# unary
grpcurl -plaintext -d '{"id":"p1"}' localhost:50051 catalog.v1.CatalogService/GetProduct

# server-streaming (each message prints as it arrives)
grpcurl -plaintext -d '{"page_size":50}' localhost:50051 catalog.v1.CatalogService/ListProducts
```
Smoke both the happy path and a missing id (expect `NotFound`) before reporting done.
