---
description: Phase 1 (spec) — read the Jira ticket and write a complete spec.md
argument-hint: "<TASK_ID>"
---

You are in the **SPEC phase** (phase 1 of 8: `spec → clarify → plan → tasks → implement → test → review → pr`).
Goal: turn the requirement for **$1** into a single, complete `spec.md`. Describe **WHAT and WHY only** —
never HOW (that belongs in `/plan`). Do not write or design code in this phase.

> Runs under Claude Code as `/spec $1`. It is also a plain runbook: any agent (pi, Qwen Code, Crush,
> opencode) can execute the numbered steps by hand — substitute `$1` with the Jira task id.

## Steps

1. **Get the requirement.**
   - If `$1` looks like a Jira key (`PROJ-1234`, `TEAM-88`): read it via the Atlassian MCP —
     `getJiraIssue` with `cloudId` + `issueIdOrKey: $1` (run `getAccessibleAtlassianResources` once if you
     don't have the `cloudId`). Pull summary, description, acceptance criteria, linked issues, comments.
   - If `$1` is empty or not a Jira key: **ask the user** for the requirement in one message
     (problem, desired outcome, affected services) and use their answer as the source. Do not invent a ticket.

2. **Derive a slug** — kebab-case, ≤ 4 words, from the ticket summary (e.g. `PROJ-1234` "Add bulk price
   import" → `bulk-price-import`).

3. **Create the spec folder and seed the file** (English only, no Russian in artifacts):
   ```bash
   mkdir -p specs/$1-<slug>
   cp templates/spec-template.md specs/$1-<slug>/spec.md
   ```

4. **Fill EVERY section** of `specs/$1-<slug>/spec.md` from the ticket/requirement. Leave no placeholder:
   - **Jira / Type / Owner** — real values; `Status: DRAFT`.
   - **Problem & goal**, **Background & context** — concrete, sourced from the ticket.
   - **Scope** — explicit in-scope AND out-of-scope bullets (out-of-scope prevents over-engineering).
   - **Acceptance criteria** — EARS style, numbered, each testable:
     `AC-1: WHEN <trigger> THE SYSTEM SHALL <observable behavior>.`
   - **Affected services / contracts** — name the actual Acme services, proto contracts, Kafka
     topics, DB tables touched (e.g. Catalog, Marketplace, `catalog.proto`, `products` table). Verify names
     against the ticket/workspace; do not guess a service that may not exist.
   - **Open questions** — list every ambiguity as an unchecked `[ ]` item; leave the **A:** blank for `/clarify`.
   - **Risks & non-functionals** — backward-compat, migration, feature-flag, performance, security.

5. **Do not tick the Review & Acceptance checklist yet** — that is gated on `/clarify` resolving all open
   questions. Status stays `DRAFT`.

## Gate / hand-off (do this as the last step)

- Print the path `specs/$1-<slug>/spec.md` and the **list of open questions** you recorded.
- Remind the user: **the spec is `DRAFT` until every open question is answered — run `/clarify $1` next**;
  do not start `/plan` or write code while questions remain.
- If you could not read the ticket (no MCP, no `cloudId`, or `$1` not provided) and the user has not given
  the requirement, **stop and ask** — do not fabricate a spec.
