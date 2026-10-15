# Delivery adapter contract

`sdlc/delivery.py` exposes `prepare`, `validate`, `publish` and `reconcile`. Delivery is selected
by the user, independently of requirements, harness or git hosting. Preparing/dry-running never
pushes, creates a branch, stages files, or calls a provider. There is no merge/deploy implementation.

```bash
python3 scripts/sdlc.py deliver patch --repo /path/to/project --work-id work-retry \
  --path src/retry.py --path tests/test_retry.py --output retry.patch --approve-local
python3 scripts/sdlc.py deliver local_branch --repo /path/to/project --work-id work-retry \
  --branch work/retry --path src/retry.py --title 'fix: make retries idempotent' --approve-local
python3 scripts/sdlc.py deliver gitlab_mr --repo /path/to/project --work-id work-retry \
  --base trunk --title 'Make retries idempotent' --body-file review.md --dry-run
```

Report/working-tree delivery returns local state without claiming checks passed. Patch exports
staged, unstaged and selected untracked files with binary changes; it performs no remote command.
An output must be new and confined to the selected repository. Commit/branch delivery requires an
empty index and explicit selected files (all safe changed files if no `--path` is provided); it
preserves unrelated work and runs existing git hooks. Secrets and runtime state cannot be delivered.
Generated paths require the effective profile to record code-generation verification.

Publication requires a clean committed feature branch, an explicit base (or discovered remote
HEAD/project policy), enabled provider integration and `--approve-external`. It always produces
a draft and never assumes GitFlow, a Jira key, or auto-merge. It uses existing `gh`/`glab` auth.
GitHub.com and GitLab HTTPS/SSH origins are supported; ambiguous/unsupported identities fail.

The publisher audits every commit being pushed, including files added and later deleted, for
secret/runtime/generated paths and bounded secret-like content checks. Git paths are literal;
pathspec expansions cannot widen selected files. It pushes the prepared immutable commit ID.
The publisher records a stable marker, checks existing provider state before creation, and persists
publishing/published/ambiguous records with a local lock under the common Git directory's
`sdlckit/deliveries` folder. A timeout never triggers a blind duplicate
create. Re-running reconciles a matching remote marker first; unresolved ambiguity requires human
inspection. Branch push is explicit and never forced. Publication bodies use temporary files rather
than shell interpolation. Provider errors report exit codes without echoing credential-bearing stderr.

For orchestrated work, pass `--runtime-db PATH --run-id ID`; the runtime must confirm the run's
required verification/review stages before delivery. The repository must be clean and its revision
must match an actual verification/review result from that same repository. Export committed worker
snapshots using `patch --since BASE_COMMIT --repo VERIFIED_WORKTREE`; the baseline must be an ancestor.
With linked runtime evidence, `--output` is resolved under the common Git directory's
`sdlckit/artifacts/RUN_ID` folder, preserving immutable verification worktrees. The returned path
identifies the artifact. Direct patches resolve output relative to the selected repository.
Direct delivery reports that it has no linked
verification evidence. Passing neither flag does not pretend that tests or review ran.

Sources: [GitHub PR create](https://cli.github.com/manual/gh_pr_create),
[GitLab MR create](https://docs.gitlab.com/cli/mr/create/).
