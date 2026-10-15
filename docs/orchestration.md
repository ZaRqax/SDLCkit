# Local orchestration and isolated workers

The coordinator is an explicit local CLI, not a hosted service or an automatically started daemon. Installation does not launch workers or polling. See [runtime/README.md](../runtime/README.md) for the exact task-plan schema, supported provider argv, commands and examples; `python3 scripts/runtime.py --help` is the authoritative installed CLI interface.

## Execution model

Normalize requirements first, identify projects/contracts and construct a task dependency DAG. A durable task records project, acceptance criteria, expected paths, input revision, owner, attempt, lease, isolated worktree, outcome and evidence. Run sequentially by default; opt in to bounded parallelism only with isolation. Separate writers for the same repository must use separate git worktrees/clones. A worktree is source isolation, not an OS/network sandbox; native harness permissions and effect gates still apply.

Only dependency-ready tasks may run. Capture actual subprocess exit/status/output and enforce worker/time/attempt/resource limits. Verification and review remain observable stages; a worker exiting zero alone does not prove unspecified acceptance checks passed. Review the combined cross-repo contracts and prepare coordinated outputs, including partial failures.

## Recovery and publication

Durable state and events distinguish queued/ready/claimed/running/blocked/failed/cancelled/completed tasks and recorded verification/review/delivery states. Retry expired/crashed workers from their recorded revisions and attempts; do not share or overwrite another writer's dirty tree. Cancellation stops new launches and terminates owned workers while preserving evidence and recoverable state.

Remote publication requires enabled capability and scoped authorization. The delivery adapter records stable idempotency keys and reconciles existing PR/MR state after an uncertain response. A remote timeout must never be retried as a blind duplicate create. Aggregated review and cross-links accompany multi-project delivery. Never auto-merge or deploy.

## Optional watches and queue

Watch/polling/webhook execution is disabled by default and must be explicitly configured and launched. Eligibility rules filter source/work/project scope; queue records persist deduplication keys, limits, attempts and audit events. Only approved safe local effects may run automatically. A watcher can enrich intake and enqueue eligible work, but source text cannot grant authority or expand allowed paths/effects.

Apply maximum queue/run/worker/time limits before launch. Turning off a watch stops new launches without deleting queued/completed run evidence. CLI status/event output provides the local status interface; no standalone web dashboard service is required. Webhook events must be scoped and deduplicated before launch. Unsupported connector/runtime features are reported explicitly.

The [optional graph engine](optional-graph-engine.md) is traceability analysis. `.claude/workflows/rlm.js` is bounded read-only recursive research. Neither is the dependency scheduler or an authorization mechanism for parallel code workers.
