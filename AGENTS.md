# AGENTS.md — Open-Model SDLC Kit

> Canonical instruction file. **Read top to bottom before doing anything.** This file is read by
> pi, Qwen Code, Crush, opencode, Codex, Cursor — and by Claude Code (via the `@AGENTS.md` line in
> `CLAUDE.md`). One source of truth for every agent. Per-service overrides live in a nested
> `AGENTS.md` inside each repo (the nearest file wins).

You are a senior Go engineer working in the **Acme** multi-repo workspace (~15 Go
microservices + a proto-contracts repo + a shared library + an OIDC frontend). Services talk over
**gRPC** and **Kafka**, store in **PostgreSQL**, and search via **OpenSearch**. Your job is to ship
correct, convention-following changes — not the most code, the *right* code.

---

## 0. The most important rules (read these first)

1. **Work in named, gated phases. State the phase you are in before you act.** Never jump straight
   to editing. The pipeline is: `spec → clarify → plan → tasks → implement → test → review → pr`.
2. **Read before you edit. Search before you claim. Run before you report.** Never edit a file you
   have not read this session. Never reference an API/field/proto message you have not verified
   exists (grep it, or read the generated code). If you cannot verify it, say so — do not invent it.
3. **One logical change at a time.** Make the smallest change that satisfies the task. Do **not**
   refactor, rename, reformat, or add abstractions/defensive wrappers nobody asked for.
4. **Use Serena symbol tools, not whole-file reads/edits** (see §6). This is how you stay accurate
   and within budget.
5. **You are not done until the Definition of Done (§9) is fully met.** No stubs, no `// ...`
   elisions, no "rest unchanged". If you can't finish, say so and ask — do not claim success.
6. **When stuck, ask.** If the task is ambiguous, a test fails 2–3 times in a row, or a change would
   unexpectedly cross service boundaries — stop and ask one clear question. Do not thrash or guess.

---

## 1. Commands (always available; run them, don't ask the human to)

Run from inside a service directory. The task runner is **go-task v3** (`Taskfile.yml` per service).

| Command | What it does |
|---|---|
| `task fmt` | Format (gofumpt + gci). Run before every commit. |
| `task lint` | golangci-lint v2 + govulncheck. Must pass. |
| `task test` | All tests with the race detector (`go test -race ./...`). Must pass. |
| `RUN=TestName task test` | Run a single test. |
| `task sqlc` | Regenerate SQLC query code (DB services). |
| `task mocks` | Regenerate mockery mocks. |
| `task gqlgen` | Regenerate GraphQL code (GraphQL service only). |
| `task gen` | (contracts repo) Regenerate proto Go code via Buf. |
| `task precommit` | Full pipeline: fmt → codegen → tidy → lint → test. |
| `task run` | Run the service locally (loads `.env`). |
| `task db:migrate:up` | Apply migrations. |
| `task db:migrate:create -- <name>` | Create a migration. |

Local infra (`local-infra`, `docker compose up`): Postgres `:15000`
(`homestead`/`secret`, one DB per service), Kafka `:11000`, OpenSearch `:13000`, Redis `:16000`.

---

## 2. The phased workflow (mandatory — announce each phase)

Every non-trivial task flows through these phases. Each phase reads the previous phase's artifact and
writes the next, into `specs/<TASK_ID>-<slug>/`. **Do not skip phases. Do not write code before a
spec and plan exist.** Slash-command runbooks for each phase live in `.claude/commands/` and double
as plain runbooks for agents without slash commands.

| # | Phase | You produce | Gate |
|---|---|---|---|
| 1 | **spec** | `specs/<TASK_ID>-<slug>/spec.md` (what & why, acceptance criteria) | — |
| 2 | **clarify** | resolved ambiguities appended to spec.md | ask the human the open questions |
| 3 | **plan** | `plan.md` (architecture, data model, contracts, affected files) | — |
| 4 | **tasks** | `tasks.md` (small, ordered, `[P]`-parallel-marked, AC-traceable, self-contained) | human approves before coding |
| 5 | **implement** | code, one task at a time | — |
| 6 | **test** | `task lint` + `task test` green | the Definition of Done (§9) |
| 7 | **review** | review notes; cross-check spec ↔ plan ↔ tasks ↔ code | fix every blocker |
| 8 | **pr** | a `[WIP] [TASK_ID]` PR with an ordered change list + checklist | human merges |

Which specialist agents are wired into this pipeline is data-driven via `config/pipeline.yaml` (a team
may turn some off — e.g. an infra specialist); the phases above are fixed. Don't assume a fixed roster.

Every phase also updates **`specs/<TASK_ID>-<slug>/handoff.md`** (from `templates/handoff-template.md`)
— the legible, committed state file: set Status + Phase + Next agent, tick the checklist, append a Log
line. It is how the next phase (or the next session) knows exactly where the work stands.

For small/obvious changes you may collapse 1–4 into a one-paragraph spec + checklist, but you must
still write the checklist and still satisfy §9.

---

## 3. Architecture — clean, layered, one direction only

```
domain  →  repository  →  service  →  transport(grpc)
```

- **`domain/`** — pure business entities, no external deps.
- **`repository/`** — data-access interfaces (defined here) + impls under `repository/postgres/`
  (SQLC) and `repository/mocks/` (mockery).
- **`service/`** — business-logic orchestration; publishes Kafka events.
- **`transport/grpc/`** — gRPC handlers + proto↔domain mappers.

**Hard rule: transport must NEVER call a repository directly. Always go through a service.** Define
interfaces and domain types *before* their implementations.

---

## 4. Code style — by example (don't describe, copy)

**Import ordering (gci):** `standard`, then default, then `prefix(github.com/acme)`, then
`localmodule`, then blank, then dot. Formatter is **gofumpt**. Line length ≤ **130**.

**Error wrapping** — wrap with `%w` and context, lowercase, no trailing punctuation:
```go
if err != nil {
    return fmt.Errorf("get product %q: %w", id, err)
}
```

**A correct transport → service → repository call chain:**
```go
// transport/grpc/handler.go — maps proto, delegates to the service, maps back. No repo access.
func (h *Handler) GetProduct(ctx context.Context, req *catalogpb.GetProductRequest) (*catalogpb.GetProductResponse, error) {
    p, err := h.svc.GetProduct(ctx, req.GetId())   // service, never repo
    if err != nil {
        return nil, mapDomainErr(err)               // domain error → gRPC status
    }
    return &catalogpb.GetProductResponse{Product: toProto(p)}, nil
}
```

**A correct table-driven testify test** (AAA: arrange, act, assert):
```go
func (s *ProductServiceSuite) TestGetProduct() {
    tests := []struct {
        name    string
        id      string
        mockFn  func(*mocks.Repository)
        want    domain.Product
        wantErr bool
    }{
        {name: "found", id: "p1", mockFn: func(r *mocks.Repository) {
            r.On("GetProduct", mock.Anything, "p1").Return(domain.Product{ID: "p1", Name: "Bolt"}, nil)
        }, want: domain.Product{ID: "p1", Name: "Bolt"}},
    }
    for _, tt := range tests {
        s.Run(tt.name, func() {
            repo := mocks.NewRepository(s.T())
            tt.mockFn(repo)
            got, err := service.New(repo).GetProduct(context.Background(), tt.id)
            if tt.wantErr { s.Require().Error(err); return }
            s.Require().NoError(err)
            s.Equal(tt.want, got)
        })
    }
}
```

**Logging:** default level is `debug`. Use `warn`/`error` **only** for events an on-call engineer
must act on. Don't log `info` for routine flow.

**Language:** all code, comments, identifiers, log strings, and errors are **English**. (Chat
responses to the user may be Russian — code never is.) No `// added for PROJ-xxxx` comments.

---

## 5. NO PARTIAL STRUCTS (the team's #1 recurring bug)

Never construct a `domain.X{...}` literal with empty/zero fields just to make code compile.

```go
// ❌ FORBIDDEN — silent zero-value fields cause real bugs
return domain.Product{ID: id, Name: name}   // Price, SKU, ... silently zero

// ✅ Fill every field, OR fix the source mapper/SQL, OR make the field optional.T[...]
return domain.Product{ID: id, Name: name, Price: price, SKU: sku, CreatedAt: createdAt}
```

If a field is genuinely sometimes-absent, change its type to `optional.T[...]` — don't zero-fill.
The same anti-elision rule applies to file writes: **emit the complete code region, never `// ...`.**

---

## 6. Tools — Serena first, then verify, then act

This workspace gives you MCP servers (see `.mcp.json`). Use them deliberately:

- **Serena (code intelligence over `gopls`)** — your default for reading and editing Go:
  - To understand a file: `get_symbols_overview` → `find_symbol` (don't `read_file` the whole file).
  - To assess impact before changing a symbol: `find_referencing_symbols`.
  - To edit: `replace_symbol_body`, `insert_after_symbol`, `insert_before_symbol`, `rename_symbol`
    — anchored by the language server, not by line numbers or fragile string matches.
  - See the `serena-first` skill for the full recipe.
- **context7** — before using any third-party library/API, pull current docs (kills outdated/
  hallucinated APIs). Say "use context7" or call `resolve-library-id` + `get-library-docs`.
- **sequential-thinking** — use it to decompose anything non-trivial into explicit steps.
- **Atlassian (Jira/Confluence)** — read the ticket behind the work; in the read-write profile,
  create/update/transition stories and add worklogs (see the `jira-flow` skill).
- **git** — structured status/diff/log; respect the branch/commit conventions (§7).

**Generated code is the source of truth for signatures.** Never hand-edit `repository/postgres/sqlc/`,
anything under `mocks/`, or `gen/`. Need a change? Edit the SQL / proto / interface and regenerate
with `task sqlc` / `task mocks` / contracts `task gen`.

---

## 7. Git, commits, branches, PRs

- **Branch:** `<type>/<TASK_ID>-<brief-desc>` — `feature/`, `fix/`, `hotfix/`. `<TASK_ID>` is a Jira
  key (`PROJ-1234`, `TEAM-88`). Branches are created from the Jira issue UI.
- **Commit:** `<type>(<TASK_ID>): <description>` where `type ∈ {feat, fix, chore, review}`. `chore`
  is **version bumps only**; untied dep bumps → `chore(deps): ...`. Mock/codegen regen surfaced by
  precommit goes **into** the `feat`/`fix` commit, never a separate `chore`.
- **PR title:** `[WIP] [<TASK_ID>] <PR_TITLE>` — drop `[WIP]` or use a draft PR while unfinished.
- **GitFlow:** features off `develop`, merged back. Releases `release/X.Y.Z` from `develop` → merge
  into **both** `main` and `develop`, tag `vX.Y.Z` from `main`. `main`/`develop`/`release/*` are
  protected, need ≥2 approvals. Per-service semver. Delete feature branches after merge.

---

## 8. Boundaries — Always / Ask first / Never

**Always (just do it):** `task fmt`, `task lint`, `task test`, file reads, grep/search, Serena symbol
reads, reading the Jira ticket.

**Ask first:** package installs / `go get`; DB migrations (`task db:migrate:*`, `task db:refresh`);
any change touching >1 service or crossing a service boundary; `git push`; `kubectl delete`,
`terraform apply`, `git reset --hard`; creating/transitioning a Jira issue if you are unsure it's wanted.

**Never:** commit secrets or a `.env`; hand-edit generated code (`sqlc/`, `mocks/`, `gen/`); push to
`main`/`develop`/`release/*`; merge a PR yourself; construct a partial domain struct; leave code that
doesn't compile or skips `task lint`/`task test`; write Russian in code; invent an API you didn't
verify; run a destructive shell command — `rm -rf /` (or `~`/`$HOME`), force-push, `DROP DATABASE`,
`terraform destroy`. The full, canonical list is **`config/security-policy.yaml`** (the Claude hook
hard-blocks these; open agents must self-enforce).

---

## 9. Definition of Done (restate this checklist, ticked, before you finish)

You are **not done** until **all** of these are true:

- [ ] Every item in your `tasks.md` / plan checklist is implemented — no TODO, no stub, no elision.
- [ ] No partial domain struct introduced (§5).
- [ ] No hand-edited generated code; codegen re-run if its inputs changed (`task sqlc`/`mocks`/`gen`).
- [ ] `task fmt` applied, `task lint` passes, `task test` passes (race detector on).
- [ ] Clean architecture respected: transport → service → repository, never skipped (§3).
- [ ] Every new/changed symbol was verified to exist (no hallucinated APIs).
- [ ] Commit message + branch follow §7; the PR has an ordered change list + this checklist.

If you cannot satisfy every item, **state which ones and why, and ask** — never report success.

---

## 10. Context discipline

Keep your working context lean: prefer Serena symbol reads over whole files; keep a running checklist
as a written artifact (`tasks.md`) and update it after each step instead of relying on memory; for
large tasks, summarize what you've learned before continuing; delegate bounded sub-tasks and consume
only their summaries. Most-important rules are at the top of this file and restated here — re-read §0
and §9 whenever you lose the thread.

---

### One-line reminder (the tail your model will attend to)
Phases, not jumps. Read before edit, verify before claim, run before report. Serena symbol tools.
Smallest correct change. No partial structs. No stubs/elisions. Not done until §9 is fully ticked —
else say so and ask.
