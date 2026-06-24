<!-- Phase 1–2 artifact. Copy to specs/<TASK_ID>-<slug>/spec.md and fill EVERY section.
     Keep it ≤ ~200 lines. Describe WHAT and WHY, never HOW (that's plan.md). -->

# Spec: <TASK_ID> — <short title>

- **Jira:** <TASK_ID> (<link>)
- **Type:** feature | fix | chore
- **Status:** DRAFT → CLARIFIED → APPROVED
- **Owner / requester:** <name>

## 1. Problem & goal
<2–4 sentences: what user/business problem this solves and the desired outcome.>

## 2. Background & context
<Links to the ticket, related specs, prior art. What exists today and why it's insufficient.>

## 3. Scope
**In scope:** <bullets>
**Out of scope (explicitly NOT doing):** <bullets — this prevents over-engineering>

## 4. Acceptance criteria (EARS style, each testable & numbered)
> Format: `AC-N: WHEN <trigger> THE SYSTEM SHALL <observable behavior>.`
- **AC-1:** ...
- **AC-2:** ...

## 5. Affected services / contracts
<Which of the ~15 services, proto contracts, Kafka topics, DB tables are touched. List by name.>

## 6. Open questions (resolved in the CLARIFY phase — do not start coding while any remain)
- [ ] Q1: ... → **A:** ...
- [ ] Q2: ... → **A:** ...

## 7. Risks & non-functionals
<Performance, backward-compat, migration, security, feature-flag needs.>

---
## Review & Acceptance checklist (must all be checked before APPROVED)
- [ ] Problem & goal are clear and agreed.
- [ ] Every AC is observable and testable (no vague "works well").
- [ ] In/out of scope is explicit.
- [ ] All affected services/contracts named.
- [ ] No open questions remain.
