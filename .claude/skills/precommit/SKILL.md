---
name: precommit
description: Run pertinent repository checks and record actual outcomes
---

# precommit

Read nearest project instructions, command manifests and changed areas. Run the repository's actual formatter, regenerate only changed generator inputs, then pertinent lint/build/tests in the correct working directory. Do not assume Taskfile, Go, testify or a race detector for unrelated stacks.

Capture argv/cwd/exit code and relevant output. Fix diagnosed failures without weakening checks. Missing dependencies remain unavailable; do not install packages, migrate databases or deploy without required authorization. A skipped command is never passed. Review the final staged diff for scope, generated paths, secret exposure and incomplete implementation before the requested local commit.

Example: for a TypeScript repository with `npm run lint` and `npm test -- --runInBand`, verify those scripts exist and dependencies are present, execute them and record each exit status. Do not substitute `task lint` or claim checks passed from file-text presence.
