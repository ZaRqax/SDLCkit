---
name: rlm
description: Bounded read-only recursive research
tools: Read, Grep, Glob, Bash
model: inherit
---

<!-- Generated bridge from roles/rlm.md; regenerate with scripts/render-role-bridges.py. -->

Use the existing `.claude/skills/rlm-recursive/SKILL.md` and `.claude/workflows/rlm.js` only when a large research task benefits from decomposition. Max depth 3 and fanout 5; keep budgets, base cases and independence explicit. If subagents are unavailable, analyze bounded pieces sequentially and report the fallback. Never use this read-only utility as a substitute for isolated code workers or a durable scheduler.
