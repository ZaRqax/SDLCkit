# Local durable runtime

The runtime is optional. Setup only generates files and never launches it. Python,
git and POSIX process groups/file locks are required for workers; use WSL on native
Windows. SQLite state is stored locally, outside repository working trees. There
is no background service, external account or model subscription requirement for
command workers.

## Record and execute a run

Save this as `run.json`, replacing both repository paths with an existing Git
repository. Commands are argv arrays, without implicit shell expansion. A shell
or script may be selected explicitly only when its complete behavior is trusted.

```json
{
  "work_id": "work-retry-fix",
  "recipe": {
    "id": "quick-fix",
    "stages": [
      {"id": "execute"},
      {"id": "verify", "needs": ["execute"]},
      {"id": "deliver", "needs": ["verify"]}
    ]
  },
  "context": {
    "task": {"complexity": "trivial", "cross_repo": false, "investigation": false, "high_risk": false},
    "policy": {"requires_review": false}
  },
  "tasks": [
    {
      "id": "implementation",
      "repo": "/absolute/path/to/project",
      "argv": ["python3", "-c", "from pathlib import Path; Path('example.txt').write_text('ready\\n')"],
      "kind": "execute",
      "effects": ["local_write"],
      "max_attempts": 2,
      "timeout": 60
    },
    {
      "id": "checks",
      "repo": "/absolute/path/to/project",
      "argv": ["python3", "-c", "from pathlib import Path; assert Path('example.txt').read_text() == 'ready\\n'"],
      "needs": ["implementation"],
      "kind": "verify",
      "effects": ["read"],
      "timeout": 60
    }
  ]
}
```

```bash
python3 scripts/runtime.py --db /path/to/workspace/.sdlc/runs/runtime.sqlite3 create --plan run.json
# Review the printed command plan and record its generated run ID.
python3 scripts/runtime.py --db /path/to/workspace/.sdlc/runs/runtime.sqlite3 execute RUN_ID --approve-local
python3 scripts/runtime.py --db /path/to/workspace/.sdlc/runs/runtime.sqlite3 status RUN_ID
python3 scripts/runtime.py --db /path/to/workspace/.sdlc/runs/runtime.sqlite3 history RUN_ID
python3 scripts/runtime.py --db /path/to/workspace/.sdlc/runs/runtime.sqlite3 delivery-gate RUN_ID
```

Use `python3 scripts/sdlc.py runtime ...` for the same interface. `--db` comes before
the runtime subcommand. An execution exit status of zero means the run reached
`verified` or `delivered`; a failure, blocked gate or cancellation returns nonzero.
Verification runs the exact declared command and records its actual exit code,
bounded output log/hash, input/output revisions, duration, attempt and worktree.
No source-editing command runs in the original project working tree.

`create` captures the original repository HEAD for each task. Source branch drift
after recording the plan does not silently change its inputs. Dependencies use
their successful captured output revisions. Context and design artifacts can be
written to `SDLC_RESULT_PATH`, which lives outside the Git tree; read, verify and
review tasks must leave the repository unchanged.

## Recipes, verification and review

Recipe stages have unique IDs, a role, `needs`, and optional `when`. Supported
conditions are booleans, `always`, `nontrivial`, `requires_review`, `high_risk`, a
boolean context field (`policy.requires_review`, `task.cross_repo`,
`task.investigation`, `task.high_risk`), `task.complexity == 'trivial'` or `!=`, and
the finite mappings `{"field":"task.complexity","equals":"standard"}`,
`not_equals`, or `in` with a list. Arbitrary expressions are rejected.

A dependency ending in `?` permits a skipped task. It never waives failed,
cancelled or blocked checks. Recipe stages selected by their conditions must have
executable tasks, and task dependencies must cover the recipe dependencies.
Task-level `stage` maps a task to a stage whose ID differs from its `kind`.
Optional `acceptance_criteria` lists source AC identifiers and `expected_paths` records relative
path estimates for task ownership/review. These estimates are audit metadata, not a filesystem
sandbox; generated-path and workspace policies remain independently enforced.
Delivery is handled by the delivery adapter, rather than arbitrary worker argv.

For a reviewed feature, add a `review` stage needing `verify` and a `kind:review`
task needing all verification tasks. The review command must independently inspect
the changes/evidence and write JSON to the path in `SDLC_RESULT_PATH`:

```json
{"passed": true, "findings": []}
```

Findings are objects with `severity` (`blocker`, `critical`, `high`, `medium`,
`low`, `info`) and supporting details. Blocker/critical/high findings block
delivery. A zero exit without the structured result fails review. The runtime
validates evidence shape and dependency coverage; it cannot judge whether a custom
review script performed a meaningful review. Choose a trusted independent reviewer.

The delivery gate requires an executed successful verify task downstream of every
execute task. When policy requires review, every verify must have a downstream
successful review. For more than one changed repository, the gate additionally
requires `integration:true` on a verify task whose ancestors cover every execute
task, and an aggregate review after all checks. Disabling review in run context
cannot waive this multi-repository gate. Failed/missing/skipped checks remain
distinct states and cannot become successful by resuming a run.

## Isolation, concurrency and recovery

Execution is sequential by default. Explicit parallel CLI execution uses
`--parallel --max-workers 2` (1..32 maximum). Each attempt gets a unique branch,
worktree, task directory and log. Repository-level advisory locks coordinate
worktree/ref allocation across coordinators and independent runtime databases.
Run leases prevent duplicate coordinators. Separate worktrees can safely edit
the same source repository. Same-repository dependency revisions are merged in
the dependent isolated tree; merge conflicts fail the attempt for review.

Successful changes receive an internal Git checkpoint using `write-tree`,
`commit-tree`, and a compare-and-swap `update-ref`. This records a recoverable
worker output, rather than a requested delivery commit. No target hook is
overridden or disabled. Delivery commits must apply the project's normal hooks;
the internal checkpoint does not claim those hooks passed. The checkpoint path
rejects `.env`, key/credential filenames, escaping symlinks, detected secret-like
content and project-configured generated paths. Generated output needs a separate
reviewed regeneration/delivery procedure. Original uncommitted source changes are
never copied, staged or committed.

Workers receive `SDLC_RUN_ID`, `SDLC_TASK_ID`, `SDLC_WORKTREE`,
`SDLC_RESULT_PATH`, `SDLC_DEPENDENCIES` (successful direct dependency results and
paths), and `SDLC_WORK_ITEM` (untrusted source data for watches). Commands must
not treat source text as execution authority.

```bash
python3 scripts/runtime.py --db STATE_DB cancel RUN_ID
python3 scripts/runtime.py --db STATE_DB stop RUN_ID
python3 scripts/runtime.py --db STATE_DB recover RUN_ID
python3 scripts/runtime.py --db STATE_DB retry RUN_ID TASK_ID
python3 scripts/runtime.py --db STATE_DB execute RUN_ID --approve-local
```

Cancel records intent, cancels unstarted tasks and signals known process groups.
Ctrl-C on `execute` stops the coordinator and its workers. Recovery only reclaims
expired attempts whose recorded process is no longer alive; it does not launch
anything. Live orphan workers must be stopped explicitly first. Linux process
start identities guard against signaling a reused PID; on platforms without
`/proc`, uncertain orphans require manual inspection. Retry retains attempt and
event history, uses a new worktree, and respects each task's `max_attempts` (1..10).
Exhausted tasks require a new reviewed run. Failed descendants and never-started
cancelled tasks become eligible for reconsideration after a dependency retry.

## Trusted commands and provider automation

Execution requires explicit `--approve-local` for the stored trusted command plan.
Effective target/workspace policy is loaded for each repository and cannot be
overridden by this approval. Direct observable push, publication, package install,
migration, deployment or destructive commands are classified and checked in
addition to their declared `effects`. External effects require
`--approve-external`; forbidden effects remain forbidden. High-risk operations
need their own `--approve-effect package_install` / `migration` / `data_change` /
`infrastructure_change` / `high_risk_change`; external approval does not grant
these effects. Unknown effects fail closed.
Direct GitHub/GitLab publication commands (`gh pr create/edit/...`,
`glab mr create/edit/...`) are refused in workers even with external approval;
use the delivery adapter's persistent reconciliation instead. A custom script is
still a trusted program, so its author must route publication through that adapter.

Worktrees and command classification are **not OS/filesystem/network sandboxes**.
An approved arbitrary program can have effects that cannot be inferred from its
argv; review the program and native harness permissions before authorizing it.
The runtime cannot enforce a monetary/token API quota inside an arbitrary program.
Unknown run/task/watch budget options, including `max_tokens` and `max_cost`, are
rejected rather than silently ignored. Use an explicitly approved provider budget
flag or a trusted metering wrapper when the provider supports a hard API ceiling.
Time, worker count, attempt count, monitored disk growth and bounded logs are
enforced locally. Disk monitoring has polling granularity and is not a filesystem
quota. Durable state and retained worktrees consume disk until explicitly archived.

For native workers select `provider:codex|claude|opencode|cursor` and supply the
exact supported argv. `probe PROVIDER` checks installed version/help. Automated
native workers need `--approve-provider` as well as local/effect approval. Codex
requires `exec` and an explicit `--sandbox workspace-write` or `read-only`.
Claude uses `--print`/`-p`; OpenCode uses `run`; Cursor requires an installed
`agent`/`cursor-agent` CLI and `--print`/`-p`. GUI `cursor` is not substituted.
The runtime rejects permission/sandbox bypass flags, provider directory changes,
and arbitrary provider configuration overrides. It inherits the model and does
not install tools, fabricate model output, or automatically approve native tool
calls. Native permissions and network confinement differ by provider; the probe
reports this limit. Authenticated live model runs are separate from local adapter
and controlled worker tests. Configure the native sandbox or container yourself
when stronger isolation is required.

## Optional approved watches

A watch config contains a fixed `template` identical to the run plan's
`recipe`/`context`/`tasks`, `repositories` as exact allowed paths, and optional
`poll_argv` plus `poll_effect:"read"`. The polling adapter is an explicitly trusted
read command returning a bounded JSON array of source events. Source credentials
remain in native CLI auth/environment. Disabled connectors must not be used by
that adapter. Events require stable `id`, optional `revision`, `project`, `labels`,
and source/provenance content. `(watch,id,revision)` is durably deduplicated.
Events cannot replace argv, effects, task templates or repository scope.
Polling checks each repository's current `read` and `local_process` policy at
registration and immediately before execution. Known external, risky and
destructive argv are refused for a read adapter even when execution/delivery
has a separate effect grant. The adapter's working directory is the first
allowlisted repository. Captured output uses a bounded pipe buffer, and polling
terminates the subprocess group on timeout, overflow, failure and leader exit.

Optional `eligibility` supports `required_labels` and `allowed_projects`. Bounds:
`max_workers` (default 1, max 8), `max_queue` (100), `max_runs_per_day` (10),
`poll_interval` (60 seconds), `poll_timeout` (30 seconds), `max_run_seconds` (3600),
`max_database_bytes` (64 MiB). Each task also bounds timeout (600 seconds), logs
(1 MiB), additional disk growth (256 MiB) and attempts (1). Events/poll output are
limited to 256 KiB. Use native provider budget flags in the approved argv where
supported; no monetary limit is invented for other providers.

```bash
python3 scripts/runtime.py --db STATE_DB watch-register approved-work --config watch.json --approve-local
# Registration and changes leave the watch DISABLED.
python3 scripts/runtime.py --db STATE_DB watch-enable approved-work
python3 scripts/runtime.py --db STATE_DB watch-serve approved-work --once
# Omit --once only for an explicitly requested foreground scheduler.
python3 scripts/runtime.py --db STATE_DB watch-status approved-work
python3 scripts/runtime.py --db STATE_DB watch-disable approved-work
```

Disabling prevents new launches and rejects new intake, preserves queued work and
all run state, and lets the current worker finish. Cancel the run to stop it.
Reconfiguration disables the watch and records fresh explicit approvals. Failed
jobs are not silently retried. Use runtime `retry`/`execute` after inspecting their
evidence. Watches can prepare verified reviewable local work; publishing remains
a separately authorized delivery action with idempotent reconciliation.

## Authenticated local webhooks

Set a random secret of at least 32 characters in the environment named by
`webhook_secret_env` (default `SDLC_WEBHOOK_SECRET`); the database stores its name,
never its value. Run `webhook-serve WATCH_ID --port 8765` in the foreground.
The listener binds only `127.0.0.1` and accepts `POST /events`. It enqueues only;
the separately approved scheduler decides when to execute.

Headers: `X-SDLC-Timestamp` (Unix seconds), `X-SDLC-Nonce` (16..100 alphanumeric,
underscore or hyphen characters), `X-SDLC-Signature` (lowercase SHA256 HMAC hex).
Sign the exact bytes `timestamp + "." + nonce + "." + raw_body` with the secret.
The five-minute freshness window, constant-time comparison, durable nonce receipt,
queue dedup, body bound and read timeout reject forged, expired or replayed events.
Use an authenticated TLS proxy for remote providers; this is not a public webhook
hosting service. Arbitrary provider webhook formats require an authorized adapter
that validates the provider signature and translates to this local envelope.

The optional RLM/graph analysis remains read-only research. It neither owns worker
leases nor edits parallel source trees, executes delivery, or enables watches.
