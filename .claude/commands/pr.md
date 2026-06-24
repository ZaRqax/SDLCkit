---
description: Phase 8 (pr) — open a [WIP]/draft PR off develop with an ordered change list + checklist, then move the Jira ticket and link the PR.
argument-hint: <TASK_ID>
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
---

You are in **Phase 8 — pr** for **$1**. Say so first. This is the last gate before a human merges.
You open the PR; you do **not** merge it yourself, and you do **not** push to a protected branch
(`main`/`develop`/`release/*`).

## 0. Gate before you touch anything — the Definition of Done must already be met
Re-read AGENTS.md §9. Do not open a PR until **every** box is true:
- `task lint` passes and `task test` passes (race detector on). Re-run them now to confirm:
  ```sh
  task fmt && task lint && task test
  ```
- No partial domain structs (§5); no hand-edited generated code (`sqlc/`, `mocks/`, `gen/` regenerated
  via `task sqlc`/`task mocks`/`task gen` if their inputs changed).
- Clean architecture respected: transport → service → repository, never skipped.
- Every acceptance criterion in `specs/$1-<slug>/spec.md` is covered by a test.
- Review notes from Phase 7 have no open blocker.

If any item fails, **stop, state which, and fix or ask** — do not open the PR.

## 1. Verify the branch is correct
Branch must be `<type>/$1-<slug>` (`feature/`/`fix/`/`hotfix/`) cut from `develop`:
```sh
git rev-parse --abbrev-ref HEAD            # expect feature/$1-... not main/develop
git fetch origin develop
git log --oneline origin/develop..HEAD     # only your $1 commits, nothing stray
```
If you are on a protected branch, **stop** — the branch is created from the Jira issue UI, not here.

## 2. Make commits conform
Every commit on the branch must read `<type>($1): <desc>` with `type ∈ {feat, fix, chore, review}`
(`chore` = version bumps only; codegen/mock regen folds into the `feat`/`fix` commit, never a separate
`chore`). Example: `feat($1): add GetProduct gRPC handler`. Fix any non-conforming subject before the PR.

## 3. Build the PR body from the template
Read `templates/pr-template.md` and fill it from the phase artifacts — do not invent content:
- **Title:** `[WIP] [$1] <concise title>` (or open as a draft). Keep `[WIP]`/draft while work is unfinished.
- **What & why:** 1–3 sentences; link the Jira issue and `specs/$1-<slug>/spec.md`.
- **Changes (ordered):** numbered list, derived from `tasks.md` and your real diff.
- **How to verify:** the exact commands a reviewer runs (`task test`, `grpcurl ...`, migrations).
- **Pre-review checklist:** keep every box from the template; tick only what is truly done.

Write the filled body to `specs/$1-<slug>/pr-body.md`.

## 4. Push the branch and open the PR with gh (draft while unfinished)
```sh
git push -u origin "$(git rev-parse --abbrev-ref HEAD)"
gh pr create --draft --base develop \
  --title "[WIP] [$1] <concise title>" \
  --body-file specs/$1-<slug>/pr-body.md
```
Drop `--draft` and `[WIP]` only once the work is genuinely finished and the checklist is fully ticked.
Capture the PR URL from `gh pr create` output. **Never** run `gh pr merge` — a human merges after ≥2 approvals.

## 5. Move the Jira ticket and link the PR (read-write profile)
Use the **jira-flow** skill. In the read-write Atlassian profile, transition $1 to the next review state
and add a comment with the PR link, via the Atlassian MCP:
```
getTransitionsForJiraIssue(cloudId, "$1")          # find the right transition id (e.g. "In Review")
transitionJiraIssue(cloudId, "$1", transitionId)
addCommentToJiraIssue(cloudId, "$1", "PR opened: <PR_URL>")
```
If you are unsure the transition is wanted, ask before transitioning.

## 6. Close out
Report: the PR URL, its draft/WIP state, the commits included, and the Jira transition you made.
Restate the §9 checklist, ticked. The gate is human merge — you are done only when the PR is open,
linked from Jira, and every Definition-of-Done box is green. If any box is not green, say which and ask.
