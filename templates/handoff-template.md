<!-- The kit's canonical per-feature state file. Lives at specs/<TASK_ID>-<slug>/handoff.md,
     committed alongside the spec trio. EVERY agent updates it as its last step: flip the checklist,
     append to the Log, set Status + Next agent. It is the legible source of truth a weaker model can
     read to know exactly where the work stands. (An optional JSON mirror — handoff/<TASK_ID>.json,
     schema in handoff/schema.json — is only for the optional automation/graph layer; ignore it
     unless you've enabled that.) -->

# Handoff: <TASK_ID> — <short title>

- **Status:** DRAFT            <!-- DRAFT·CLARIFIED·APPROVED·IN_PROGRESS·TESTING·IN_REVIEW·DONE·BLOCKED -->
- **Phase:** spec              <!-- spec·clarify·plan·tasks·implement·test·review·pr -->
- **Branch:** —               <!-- <type>/<TASK_ID>-<slug> -->
- **Jira:** <TASK_ID>
- **Next agent:** planner

## Pipeline checklist
- [ ] Spec written (planner)
- [ ] Clarified — no open questions (planner)
- [ ] Plan written (tech-designer)
- [ ] Tasks approved by human (tech-designer)
- [ ] Implemented (engineer)
- [ ] Test plan + tests green (qa-lead)
- [ ] Reviewed — no blockers (go-code-reviewer)
- [ ] PR opened (engineer)

## Quality gates
| Gate | Status |
|---|---|
| lint | pending |
| test | pending |

## Decisions
<!-- append: - <decision> (confidence 0.0–1.0, reversibility easy/medium/hard) -->

## Blockers
<!-- append: - [category] <detail>  — categories: type-error, missing-auth, test-failure,
     contract-mismatch, infra-error, needs-clarification, scope-expansion -->

## Log (append-only — newest last)
- _<phase>_ <agent>: <what changed / files touched / notes for the next agent>
