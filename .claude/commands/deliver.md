---
description: Prepare the selected local artifact or authorized publication
argument-hint: "<work-id, source, or request>"
---

Read the requested target from `$ARGUMENTS` or work-item state and use `roles/delivery.md`. Supported targets include report, working_tree, patch, commit, local_branch, github_pr and gitlab_mr. Default to the configured local delivery; do not infer a PR request from a GitHub remote.

Prepare the change summary, ordered changes, acceptance coverage and real verification results. Use `templates/delivery-template.md`. Local patch/branch work must cause no remote mutation. For publication validate enabled provider capabilities, base branch and explicit scoped authorization; use an idempotency key and reconcile after uncertain responses before retrying. Record links and unavailable capabilities truthfully. Never auto-merge, deploy or transition an issue as a side effect.
