---
name: requirements-clarify
description: >
  Use BEFORE designing or coding whenever a requirement, ticket, or user request is vague,
  under-specified, or has gaps — "add sorting", "make it faster", "support exports", "handle errors".
  Scans the ask across fixed dimensions, lists the gaps as concrete questions, PROPOSES answer options
  (recommended first), tries to answer each itself, and only escalates to the human the questions it
  genuinely cannot resolve. Triggers: ambiguous request, missing detail, "it depends", unspecified
  fields/order/actors/edge cases, a feature with no acceptance criteria.
---

Turn a vague ask into a decided one. Every gap you leave silent becomes a wrong assumption shipped as
code. Your job is to surface the gaps, **propose the answers yourself**, resolve what you can defend,
and ask the human only what you cannot.

This is the reusable technique behind pipeline phase 2 (`/clarify`). `/clarify` applies it to a
`spec.md` against the Jira ticket; this skill is the general form any agent uses at any phase the
moment a request turns out to be under-specified.

## When to run it

Run it the instant an instruction stops being concrete. Signals: a verb with no object ("handle
errors", "support filtering"), a noun with no fields ("add sorting", "add pagination"), no actor
("who triggers this?"), no observable outcome ("works well"), or a choice you would otherwise make
silently. If you are about to *guess* a decision that changes behavior — stop and run this instead.

## Workflow

1. **Restate the ask in one sentence.** If you cannot, the first gap is the goal itself — ask that
   before anything else.

2. **Gap-scan the ask across these dimensions, in order.** For each, either note "settled" (with the
   evidence) or open a gap. Absence of a stated answer IS a gap.

   | # | Dimension | The question it asks |
   |---|---|---|
   | 1 | **Goal & success** | What does "done" look like, observably? How is success measured? |
   | 2 | **Actors & personas** | WHO uses this (B2C buyer / B2B ops / admin / system)? In what context, how often? |
   | 3 | **Trigger & input** | What starts it? What exactly comes in (fields, types, ranges, empty/absent)? |
   | 4 | **Data & fields** | Which fields/entities are involved? For sorting/filtering/search: WHICH columns? |
   | 5 | **Behavior & ordering** | For sorting: by which fields, what direction, what tie-breaker, single or multi-key? For flows: what order, what happens on each branch? |
   | 6 | **Edge & error cases** | Empty input, duplicates, negatives, too-large, concurrent, unauthorized, not-found? |
   | 7 | **Scope boundary** | What is explicitly OUT? Which "obvious" case is neither in nor out? |
   | 8 | **Integration** | Does it imply a contract/proto change, a new topic/table, a second service, a migration? |
   | 9 | **NFRs** | Latency/throughput targets, backward-compat, idempotency, auth/tenant scoping, feature flag? |
   | 10 | **Acceptance** | Can each behavior be written as `WHEN <trigger> THE SYSTEM SHALL <observable>`? If not, what's missing? |

3. **For every gap, propose answers and try to resolve it yourself.** Do not ask an open question —
   offer a short menu with a recommended default, then attempt your own answer:
   - **Verify first.** Grep/read the code, ticket, or contract. A gap that the codebase already answers
     ("which field is the timestamp? → `created_at`, see `domain/product.go:14`) is **RESOLVED**, not a
     question. Cite the evidence.
   - **Decide the decidable.** A gap with one defensible engineering default (tie-break by stable id,
     newest-first default, server-side when pagination exists, single-key for v1 per YAGNI) is
     **RESOLVED** — state the assumption and proceed. These are yours to own; don't waste the human on
     them.
   - **Escalate only the genuinely open.** A gap that is a *product/business* decision, has two
     defensible answers, or depends on a fact you cannot verify → **NEEDS-USER**.

4. **Ask the human in one message, numbered, each with options + a recommended default** so every
   question is answerable in a word. Lead with the NEEDS-USER list; below it, list the assumptions you
   already RESOLVED so the human can veto any of them. Then STOP and wait.

5. **Record the outcome.** Write each answer (or confirmed assumption) back into the artifact in play —
   `spec.md §6` during clarify, a `## Decisions` note in `plan.md` during design, or a short comment in
   the task during implementation — so the decision survives the session and the next agent sees it.

## Worked example

The user says: **"We need to add sorting to the product list."**

Gap-scan produces (dimension → gap → proposed options → self-answer → verdict):

```
CLARIFY "add sorting to the product list" — 2 questions need you; 4 I resolved (veto any).

NEEDS-USER:
1. Which fields are sortable?
   (a) name, price, created_at  [recommended]   (b) every scalar field   (c) price only
   → product decision; I can't infer it from the code. Pick a/b/c or list fields.
2. Who is this for and how do they use it — B2C buyers browsing, or B2B ops reordering?
   → changes the default sort and whether price is exposed. One line is enough.

RESOLVED (assumptions — say "no" to any and I'll reopen):
3. Default sort + direction → created_at DESC (newest first). Common catalog default.
4. Single-key vs multi-column → single-key for v1 (YAGNI); multi-key is a later story.
5. Server-side vs client-side → server-side (SQL ORDER BY): the list is already paginated,
   client-side sort of one page would be wrong. Verified pagination in transport/grpc/handler.go.
6. Tie-breaker → stable secondary sort by id, so equal keys keep a deterministic order.
```

Note the shape: every question carries its options and a recommended default; the resolvable ones were
resolved with evidence and surfaced for veto; only the two genuine product decisions were escalated.

## Rules

- **Never ask an open question when you can offer a menu.** Options + recommended default, always.
- **Self-answer first.** Verify against code/ticket/contract; decide the decidable; escalate only what
  is genuinely a business call or unverifiable. The human should receive a short list, not a questionnaire.
- **One message, then stop.** Do not guess answers to unblock yourself; do not trickle questions one by one.
- **Separate NEEDS-USER from RESOLVED.** The human must see both — to answer the first and veto the second.
- **Verify before you claim** a field/endpoint/behavior exists; if you can't confirm it, that itself is a
  question, not an assumption.
- **Record every decision** back into the artifact so it outlives the conversation.
- **English** in the artifact; ask the human in their language if they prefer.
