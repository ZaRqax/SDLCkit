---
description: Review correctness and evidence using the generic reviewer
argument-hint: "<work-id, source, or request>"
---

Use `roles/reviewer.md` for the scoped diff and actual verification evidence. Determine the comparison base from project policy and locally available git metadata; do not assume develop or fetch remote data unnecessarily.

Read enclosing symbols/callers, verify candidate defects and self-refute before reporting. Include file/line, impact, severity and confidence. Review acceptance coverage and combined cross-repo effects. Return pass, changes_requested or unverified. Repair blockers before delivery. The optional Go reviewer applies only to an explicitly selected Go profile.
