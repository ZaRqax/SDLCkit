---
description: Compatibility alias for explicitly requested GitHub PR delivery
argument-hint: "<work-id, source, or request>"
---

This retained command is a GitHub-specific alias for `/deliver github_pr`. Read `.claude/commands/deliver.md`, the target project policy and actual evidence. The alias chooses a deliverable; it does not bypass external-write approval, enable a connector, select develop or transition a tracker issue.

Prepare a reviewable body from `templates/pr-template.md`. Publish only with explicit authorization, supported GitHub capability and reconciliation/idempotency checks. If GitHub is unavailable or unauthorized, return the prepared artifact and exact blocked reason. Do not silently switch to another provider or claim publication.
