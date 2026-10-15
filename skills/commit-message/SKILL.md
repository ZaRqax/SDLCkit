---
name: commit-message
description: Prepare local commits using the target repository conventions
---

# commit-message

Read the target repository's existing commit/branch conventions and the requested delivery. Preserve an upstream issue ID if provided; never invent a Jira key or require a tracker. Use an internal work ID in artifacts when no upstream reference exists.

Follow the local convention; if none exists, a concise conventional commit such as `fix: preserve stable sorting for equal timestamps` is a reasonable default. Include regenerated code with its source change. Stage only intended files, inspect the diff, exclude secrets/local state and record relevant verification before committing.

A local commit request does not authorize push, PR/MR publication, issue comments, merge or deploy. Do not select develop or a protected base without project evidence. Models and harnesses inherit user settings.
