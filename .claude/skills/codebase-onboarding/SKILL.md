---
name: codebase-onboarding
description: >
  Use before editing an unfamiliar service repo in this workspace — first contact with a service you
  haven't touched this session. Builds a compact map (stack, entrypoints, test commands, layering)
  so you don't burn context groping around. Invoke with /codebase-onboarding for the full reference.
---

# codebase-onboarding — a compact map before you touch an unfamiliar service

Standalone runbook. Goal: spend a few minutes building a durable, compact map of a Acme service so
every later step is cheap and accurate. The symbol-level *mechanics* live in the **serena-first**
skill — this skill is the order of operations for first contact. Do this once per service repo; the
output is reusable across sessions because it lands in committed Serena memories.

## Steps

1. **Read the orientation files, nearest-first.** The service's own `AGENTS.md` (nested, nearest wins)
   → `Taskfile.yml` (the real build/test/codegen commands) → `README` → `.mcp.json`. These tell you
   the stack, the commands, and any service-specific overrides before you read a line of Go.
2. **Map the entrypoints.** Look at `cmd/` — `cmd/grpc-server/` (main RPC entry), `cmd/kafka-consumer/`,
   `cmd/seeder/`. That tells you what the service *is* (gRPC server, Kafka consumer, both).
3. **Let Serena onboard.** On first Serena use against the repo, allow onboarding to run — it writes
   `.serena/memories/*.md` and `.serena/project.yml`. Ensure `GITHUB_PAT` is in the env so gopls can
   index private `github.com/acme` modules (else `find_symbol` is empty on private code).
4. **Skim the layers with symbols, not full reads.** `get_symbols_overview` on `internal/domain/`,
   `internal/service/`, `internal/transport/grpc/` to confirm the standard
   `domain → repository → service → transport` shape and spot where this service deviates.
5. **Record the map.** Capture it in a Serena memory (it persists and is committed). Keep it to the
   template below — a map, not a transcript.

## Output template (store as a Serena memory)

```markdown
# Onboarding: <service>
## Stack         — Go + gRPC/Kafka/Postgres/OpenSearch? which of these?
## Entrypoints   — cmd/* binaries and what each does
## Key packages  — domain / repository / service / transport (+ any extra: validator, mapper, cache)
## Commands      — task fmt | lint | test | sqlc | mocks | run | db:migrate (from Taskfile.yml)
## Architecture  — deviations from the standard layering, factories, event producers
## Risk areas    — generated dirs (sqlc/mocks/gen), partial-struct hotspots, cross-service calls
## Unknowns      — what you still don't understand (resolve before editing those areas)
```

## Worked example

First contact with the **catalog** service: nested `AGENTS.md` says it owns Products/Categories/
Documents/Assemblies; `Taskfile.yml` has a `sqlc` target (so it has a DB) and a `kafka-consumer`
binary (so it emits/consumes events). `get_symbols_overview internal/repository/` shows a **factory**
selecting product-type-specific behavior — the one real deviation worth noting. Map → Serena memory.
Now an edit to "add a field to Product" starts from `domain.Product` + the sqlc query, not a blind grep.

## Rules

- **Map, don't memorize.** Capture structure and commands; do not paste whole files into the map.
- **Symbols over file reads** (serena-first): `get_symbols_overview` / `find_symbol`, not `read_file`.
- **Commit the Serena memories** (`.serena/memories`, `.serena/project.yml`); they give every future
  session free context. `.gitignore` already excludes `.serena/cache/`.
- **Don't act on guesses.** If an "Unknown" touches the area you're about to change, resolve it first
  (read the symbol, ask) — never edit blind. English only.
