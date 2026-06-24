---
name: commit-message
description: >
  Use when committing or naming a branch: conventional commits with the Jira task id. Covers
  branch naming, the <type>(<TASK_ID>): <desc> format, and what does/doesn't get its own commit.
  Invoke with /commit-message for the full reference.
---

# commit-message — branches & conventional commits

Read the Jira key off the branch or the ticket first — every commit and branch is tied to one
(`PROJ-1234`, `TEAM-88`). If you can't find the task id, stop and ask; do not invent one.

## Branch name

`<type>/<TASK_ID>-<brief-desc>` — `type ∈ {feature, fix, hotfix}`. Lowercase, hyphenated, imperative,
no trailing slash junk. Branches are created from the Jira issue UI (off `develop`).

```
feature/PROJ-1820-offer-price-tiers
fix/TEAM-204-nil-deref-in-product-mapper
hotfix/PROJ-1999-block-negative-inventory
```

## Commit message

`<type>(<TASK_ID>): <description>` — `type ∈ {feat, fix, chore, review}`. Imperative mood,
lowercase first word, **no trailing period**, ≤ ~72 chars on the subject line.

```
feat(PROJ-1820): add price-tier resolution to offer service
fix(TEAM-204): guard nil supplier in product mapper
review(PROJ-1820): apply reviewer feedback on tier validation
chore(deps): bump contracts-go to v1.42.0
```

### Type rules (the parts people get wrong)

- **`feat` / `fix`** — the actual change. Mock/codegen regen surfaced by `task precommit`
  (`task mocks`/`sqlc`/`gen`) goes **INTO this same commit**, never a separate `chore`. If you
  changed an interface and regenerated mocks, it's all one `feat`/`fix`.
- **`chore` = version bumps ONLY** — dependency, toolchain, or tool-binary bumps. Nothing else.
- **Dep bump not tied to a task** → `chore(deps): ...` (no `TASK_ID`). This is the one allowed
  form without a Jira key.
- **`review`** — commits that apply reviewer feedback during PR review; keep the same `TASK_ID`.

### Worked example: interface change + regenerated mocks → ONE commit

```bash
# edited internal/repository/repository.go (added a method), then:
task mocks            # regenerates internal/repository/mocks/ — generated, never hand-edited
task fmt && task lint && task test
git add internal/repository/ internal/service/
git commit -m "feat(PROJ-1820): add ListOffersByTier to offer repository"
# the regenerated mocks ride along in this feat commit — do NOT split them into chore(...)
```

## Never commit

- **Secrets / `.env`** — check `git status` before staging; if a secret is staged, unstage and stop.
- **Hand-edited generated code** (`repository/postgres/sqlc/`, `mocks/`, `gen/`) — regenerate with
  `task sqlc`/`task mocks`/`task gen` instead; commit the regenerated output, not manual edits.
- **A partial domain struct** — if your diff zero-fills a `domain.X{...}`, fix it before committing
  (fill every field or make the field `optional.T[...]`); see AGENTS.md §5.

Before you commit: `task fmt && task lint && task test` are green. Never push to
`main`/`develop`/`release/*`. Subject line is imperative, lowercase, no period, has the `TASK_ID`.
