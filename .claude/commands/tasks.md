---
description: Build an acceptance-traceable dependency task list
argument-hint: "<work-id, source, or request>"
---

Read the requirement and plan. Use `templates/tasks-template.md` to produce small self-contained tasks, each with stable ID, project, dependencies, estimated paths, acceptance criteria and completion evidence. Mark parallel eligibility only for independent tasks that can run in isolated worktrees.

Persist machine-readable task dependencies when using the runtime. One role may perform multiple steps; do not create unnecessary agents. Stop for approval only when the effective project policy requires it and authorization is not already present. A missing/skipped stage must not be marked completed.
