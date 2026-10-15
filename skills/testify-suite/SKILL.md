---
name: testify-suite
description: >
  Use when writing Go unit tests: testify suite + table-driven cases, AAA, mockery mocks, race
  detector. Invoke with /testify-suite for the full reference.
---

> Optional Go profile capability. Apply only when the target repository uses this stack/toolchain; nearest project instructions and effective policy determine commands, architecture and authorization. This runbook is not a default dependency of generic workflows.

# testify-suite — table-driven testify suites for service-layer Go

Standalone runbook. You are writing unit tests for a Acme service. Tests live next to the
code under test (`internal/service/foo_test.go`), use the **testify suite**, are **table-driven**,
follow **AAA** (arrange / act / assert), and drive collaborators through **mockery** mocks. Run with
the race detector.

## Steps

1. **Find the contract under test, not the implementation.** Use Serena: `find_symbol` on the
   service method; note its signature, returned domain types, and the repository interface it calls.
2. **Confirm the mock exists.** Mocks are generated, never hand-written. If the interface changed or
   the mock is missing, regenerate: `task mocks`. Never edit anything under `mocks/`.
3. **Write the suite struct + entry point** (one `suite.Run` per test file).
4. **Write one table-driven test method per service method.** One row = one behavior. Each row owns
   its mock setup via a `mockFn` closure so cases stay independent.
5. **Run it:** `RUN=TestProductServiceSuite task test` (single suite) or `task test` (all, race on).

## Worked example

Testing `service.New(repo).GetProduct(ctx, id)` which returns a `domain.Product` or wraps the repo
error. The repository is reached through the `Repository` interface; its mock is `mocks.Repository`.

```go
package service_test

import (
    "context"
    "errors"
    "testing"

    "github.com/stretchr/testify/mock"
    "github.com/stretchr/testify/suite"

    "github.com/acme/catalog/internal/domain"
    "github.com/acme/catalog/internal/repository/mocks"
    "github.com/acme/catalog/internal/service"
)

type ProductServiceSuite struct {
    suite.Suite
}

func TestProductServiceSuite(t *testing.T) {
    suite.Run(t, new(ProductServiceSuite))
}

func (s *ProductServiceSuite) TestGetProduct() {
    errNotFound := errors.New("not found")

    tests := []struct {
        name    string
        id      string
        mockFn  func(*mocks.Repository)
        want    domain.Product
        wantErr bool
    }{
        {
            name: "returns product when repository has it",
            id:   "p1",
            mockFn: func(r *mocks.Repository) {
                r.On("GetProduct", mock.Anything, "p1").
                    Return(domain.Product{ID: "p1", Name: "Bolt", SKU: "B-1", Price: 10}, nil)
            },
            want: domain.Product{ID: "p1", Name: "Bolt", SKU: "B-1", Price: 10},
        },
        {
            name: "propagates repository error",
            id:   "missing",
            mockFn: func(r *mocks.Repository) {
                r.On("GetProduct", mock.Anything, "missing").
                    Return(domain.Product{}, errNotFound)
            },
            wantErr: true,
        },
    }

    for _, tt := range tests {
        s.Run(tt.name, func() {
            // arrange
            repo := mocks.NewRepository(s.T()) // s.T() auto-asserts expectations at cleanup
            tt.mockFn(repo)

            // act
            got, err := service.New(repo).GetProduct(context.Background(), tt.id)

            // assert
            if tt.wantErr {
                s.Require().Error(err)
                return
            }
            s.Require().NoError(err)
            s.Equal(tt.want, got)
        })
    }
}
```

## Rules

- **Test the contract, not the implementation.** Assert on returned domain values and errors, not on
  private fields or call order you don't care about. A refactor that preserves behavior must not
  break the test.
- **One behavior per case.** Found vs. not-found vs. validation-error are separate rows, each named
  for the behavior it pins down. Don't cram two assertions of different behaviors into one row.
- **No partial `want` structs.** The expected `domain.Product` is fully populated — matching the
  no-partial-structs rule (§5). A zero-filled expectation hides real mapping bugs.
- **`mocks.NewRepository(s.T())`** binds the mock to the test `T`: unmet `.On(...)` expectations fail
  the test automatically at cleanup. Use `s.Require()` to stop a failed case before a nil deref;
  use `s.Equal`/`s.Error` for plain assertions.
- **Generated mocks are read-only.** Interface changed → `task mocks`, never hand-edit `mocks/`.
- **Run with the race detector:** `task test` (or `RUN=<SuiteName> task test`). Both must be green
  before you call the work done.
- **English only** in test names, comments, and messages.
