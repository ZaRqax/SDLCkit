---
id: rlm
purpose: Bounded read-only recursive research
capabilities:
- read
- review
allowed_effects:
- read
outputs:
- review.md
handoff:
  record: handoff.md
  include:
  - evidence
  - limitations
---

Use the existing `.claude/skills/rlm-recursive/SKILL.md` and `.claude/workflows/rlm.js` only when a large research task benefits from decomposition. Max depth 3 and fanout 5; keep budgets, base cases and independence explicit. If subagents are unavailable, analyze bounded pieces sequentially and report the fallback. Never use this read-only utility as a substitute for isolated code workers or a durable scheduler.
