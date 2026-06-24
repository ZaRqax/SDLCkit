---
description: Phase 2 (clarify) — close open questions in a spec before planning starts.
argument-hint: <TASK_ID>
allowed-tools: Read, Edit, Glob, Grep, mcp__atlassian__jira_get_issue
---

You are in **Phase 2: CLARIFY** of the pipeline `spec → clarify → plan → tasks → implement → test → review → pr`.
State the phase out loud before you act. Your job is to find and resolve every ambiguity in the spec
**before** any planning happens. You do NOT write `plan.md`. You do NOT write code.

**Gate:** planning is blocked while a single open question is unresolved. You leave this phase only by
setting `Status: CLARIFIED` with §6 fully answered. If you cannot answer a question yourself, ASK the human.

## Workflow

1. **Locate the spec.** Resolve the slug folder for `$1`:
   ```
   Glob: specs/$1-*/spec.md
   ```
   Read the file. If none exists, stop and say: "No spec for `$1` — run `/spec $1` first." Do not invent one.

2. **Re-read the ticket for ground truth.** Pull the Jira issue so you clarify against the real ask,
   not the spec author's paraphrase:
   ```
   mcp__atlassian__jira_get_issue(issue_key="$1")
   ```
   If Atlassian is unavailable, note it and clarify from the spec alone.

3. **Run a coverage pass.** Read every section and hunt concrete gaps in these four areas:
   - **Scope gaps (§3):** any in-scope behavior with no AC? any "obvious" case (errors, empty input,
     pagination, auth) neither in- nor out-of-scope?
   - **Ambiguous ACs (§4):** vague verbs ("handle", "support", "works well"), unstated triggers, no
     observable outcome. Every AC must be `WHEN <trigger> THE SYSTEM SHALL <observable behavior>`.
   - **Unstated NFRs (§7):** performance/latency targets, backward-compat, migration ordering, feature
     flag, idempotency of Kafka consumers, auth/tenant scoping. Absence is itself a question.
   - **Affected-services completeness (§5):** does a stated change imply a proto/contract edit, a new
     Kafka topic, or a second service not listed? Grep to confirm a named symbol actually exists before
     treating it as settled — never assume an API. e.g. `Grep: "GetProduct" path:catalog`.

4. **Ask the human the open questions as a numbered list.** One message, concrete, each answerable in a
   sentence. Offer a default where you have a sensible one. Example:
   ```
   CLARIFY $1 — 3 open questions block planning:
   1. AC-2 says "sync inventory" — which direction (Catalog→Marketplace, both)? Default: Catalog→Marketplace.
   2. Is the new `stock_level` field nullable, or 0 when unknown? (No partial structs downstream — needs a real answer.)
   3. §5 lists Marketplace only; does this also touch the Search index (OpenSearch reindex)? yes/no
   ```
   Then STOP and wait. Do not guess answers to unblock yourself.

5. **Record answers into §6.** For each question, tick it and write the answer inline. Use Edit on the
   exact `- [ ] Qn:` line — keep the file's existing shape, do not rewrite whole sections:
   ```
   - [x] Q1: Sync direction? → **A:** Catalog→Marketplace only; reverse is out of scope (added to §3).
   ```
   If an answer changes scope or an AC, also Edit §3/§4 to match, so the spec stays self-consistent.

6. **Verify the gate, then flip status.** Confirm no `- [ ]` remains in §6. Only then Edit the status line
   (template ships it as `- **Status:** DRAFT → CLARIFIED → APPROVED`) to read exactly:
   ```
   - **Status:** CLARIFIED
   ```

## Rules

- English only in the spec file. Ask the human in the user's language if they prefer; the artifact stays English.
- Do NOT proceed to `/plan` while any §6 question is unresolved — this is the phase gate.
- Do NOT add implementation detail (HOW) — that belongs in `plan.md`. Clarify WHAT and WHY only.
- Verify before you claim: grep/read for any service, field, or proto message you reference; if you can't
  confirm it exists, that becomes an open question, not an assumption.
- Smallest edits: change only the lines that need changing (§6, and §3/§4 if an answer moves scope).

## Handoff (last step)

End with: which questions were resolved, that §6 is fully ticked, that `Status: CLARIFIED` is set, and the
one-line gate reminder: **"Spec CLARIFIED. Run `/plan $1` next — planning was blocked until now."** If any
question is still open, say so explicitly and do NOT set CLARIFIED.
