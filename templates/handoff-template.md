# Handoff — <Work ID>

- State: <queued | running | blocked | failed | completed | cancelled>
- Stage: <selected recipe stage>
- Workflow: <recipe>
- Projects / worktrees: <IDs, paths, owners and input revisions>
- Next action / owner: <concrete action>
- Updated at: <UTC timestamp>
- Requested delivery / result: <target and artifact or URL>

## Progress and evidence

| Task / stage | State | Evidence / exit code | Next dependency |
|---|---|---|---|
| <id> | <pending/running/passed/failed/skipped/unavailable> | <path> | <id> |

## Decisions, authorization and blockers

<Scope, approvals, outstanding questions, unavailable checks and retry/reconciliation notes. Never include credentials.>

## Log

- <UTC> <stage/owner>: <observed change, evidence and next action>
