---
name: codebase-onboarding
description: Map an unfamiliar repository before editing
---

# codebase-onboarding

Read nearest repository instructions, README, manifests, CI and build/test entrypoints. Record stack, ownership, verified commands, generated paths, actual architecture, dependencies and risks in a concise context artifact. Use grep, file reads, LSP or optional Serena as appropriate.

Detection is evidence, not authority to execute installs/migrations/deployments. Keep unknowns explicit, do not read secret values, and cite paths/revisions for material findings. Projects stay in their existing directories. Use the deterministic discovery/installer for configuration; do not handcraft a second unmanaged installation.

Example: a Python repository declares pytest in pyproject.toml and has an existing AGENTS.md. Preserve those instructions, verify available test tooling, map the relevant package/tests and report missing commands honestly. No Go Taskfile or Jira account is implied.
