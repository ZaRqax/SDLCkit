# Verification: work-20261015

## Executed checks

- `bash scripts/check-kit.sh --test`: structural/schema/role-drift validation plus the complete
  offline unit/integration suite; 132 tests pass. Includes actual installed Codex/Claude parsers.
- `python3 -m ruff check sdlc scripts tests`: passes (E9/F correctness rules).
- `python3 scripts/sdlc.py config validate`: workspace schema and recipe references pass.
- `git diff --check` and `git diff --cached --check`: pass.
- Shell/Python/JSON/YAML syntax, canonical role/skill bridges and default neutrality are checked
  by the structural verifier. Provider-native config snapshots are asserted in harness tests.
- Commit safeguards run against the complete staged change before the requested local commit.

The kit has no service Taskfile or Go module. Go service fmt/lint/race commands are not applicable
to this Python/shell/instruction repository. Disposable Go projects verify discovery/profile
selection; existing project commands are suggested rather than installed or silently executed.

## Acceptance and source matrix

| Source matrix / AC | Evidence |
|---|---|
| A, B, C, D, G / AC-1–5 | `test_end_to_end`: real external workspace with Go/Python/TypeScript repos, no account/remote, preserved instructions, native outputs and repeated installation |
| E / AC-6–7 | `test_integrations` fetch provenance plus `test_delivery` local patch without provider calls; disabling integrations blocks invocation |
| F / AC-7 | GitLab publisher command double checks explicit authorization, draft/body-file arguments, pinned revision, reconciliation and single create; no live MR created |
| H / AC-5–6 | Missing executable/capability errors, bounded MCP stdio lifecycle, unsupported transport/budget reporting and native fallback metadata |
| I / AC-3–4 | Installer tests cover zero-write preview, idempotency, owned/unowned conflicts, recovery, symlinks, paths with spaces, partial uninstall and disjoint allowed project roots |
| J / AC-9 | Legacy setup tests cover six positional harnesses, check/pipeline/list/uninstall and five-column old manifests using private fixture homes |
| K / AC-11 | Worker tests execute real concurrent processes in distinct worktrees of the same/different repositories, with durable leases and dependency propagation |
| L / AC-8, AC-10–12 | Actual failed checks, worker exit/crash, cancellation/retry/recovery, immutable input revisions, log/output tampering, bounded subprocesses and ambiguous publication |
| M / AC-6, AC-13 | Source text stays untrusted data; watch payload cannot replace approved argv/repository/effects; pathspec magic and secret history/content are rejected |
| N / AC-13 | No implicit installs; denied/scoped external and high-risk operations fail before execution; inherited deny rules cannot be approved away |
| AC-12 | Real polling → queue → isolated execution → verify; localhost HTTP HMAC/replay tests; disabled watches prevent launches while retaining state |
| AC-14–15 | Complete suite, schemas, CLI smoke, lint, independent review fixes and one local delivery commit |

## Provider checks and explicit limits

Codex 0.162.1 and Claude Code 2.1.201 parsed generated configuration with nonempty native role
files. OpenCode 2.0.29 version/help were probed; its private-home `debug config` exceeded a
15-second smoke deadline and is not reported as passed. Cursor Agent CLI is unavailable here;
its rules/CLI configuration are covered by deterministic format snapshots, without live IDE
attachment verification. See `harnesses/README.md` for provider references and capability limits.

No paid model execution, external account mutation, live issue retrieval, push, real PR/MR,
production operation or real background watch was performed. Provider command doubles test
publication behavior without credentials. Installed tools/auth and provider-side policies must
be checked on actual authorized use. Worktrees isolate source ownership, not arbitrary process
filesystem/network effects. Native permissions vary. Token/monetary ceilings for arbitrary
programs are explicitly unsupported; unknown budgets fail, and local time/log/disk/concurrency/
queue/attempt bounds are enforced instead. Native Windows workers require WSL/POSIX.
