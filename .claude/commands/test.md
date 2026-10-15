---
description: Run relevant project checks and preserve real evidence
argument-hint: "<work-id, source, or request>"
---

Read acceptance criteria, changed files and actual project commands. Follow `roles/verifier.md`. Run pertinent tests plus required formatting/lint/build/integration checks, capture argv/cwd/time/exit code and output in verification artifacts. Map criteria to evidence.

Record passed, failed, unavailable, skipped and not-run distinctly. Never assume Taskfile, Go or a race flag in an unrelated stack. Do not install dependencies or modify data without required authorization. Fix diagnosed failures without weakening tests. Unavailable checks must be reported as gaps, not green gates.
