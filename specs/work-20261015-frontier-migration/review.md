# Review: work-20261015

Reviewed the integrated change against the full supplied migration roadmap and acceptance criteria.
Independent reviewers inspected source/delivery/storage, config/installer/harness and runtime/watch
boundaries. All actionable blockers found in that review were repaired and covered by regressions.

## Repaired blockers

1. Taskfile-only Go defaults and active review instructions assumed Acme/develop/spec/Serena.
   Generic Go uses actual project commands; the deep reviewer derives the actual local comparison
   base and retains severity/confidence/self-refutation. Historical Acme material is optional.
2. Explicit installer config could bypass target policy, and generated native rules could permit
   approval of a forbidden effect. Project profiles merge with validated safety precedence;
   native output derives effective effect decisions and documents unsupported native enforcement.
3. Setup did not persist discoverable source settings and rejected reviewed disjoint roots.
   Manifest-owned workspace source now survives reload; each target owns its scoped project subset
   while retaining the full validated registry and explicit allowlist.
4. Remote preparation audited only dirty files. Every pushed commit is now audited, including
   secret files added and later removed, and secret-like file contents. Literal Git paths prevent
   magic pathspec expansion from broadening selected files.
5. Publication used mutable HEAD and could return stale local delivery success. Pushes use the
   prepared immutable revision; provider reconciliation confirms the expected head SHA. Reused
   work IDs cannot report a different local change as committed. Ambiguous outcomes do not
   trigger blind duplicate creation.
6. Delivery artifacts/journals dirtied immutable verification trees. Journals and linked-run patch
   artifacts now live in confined Git metadata; delivery checks repository identity/revision,
   records durable results, and leaves retained worker evidence valid after repeat delivery.
7. Polling trusted a declared read effect without enforcing policy and could leave orphan children.
   Registration/execution both check current policies/classification for every allowed repository;
   bounded output and process-group cleanup cover timeout, overflow and leader exit.
8. Worker inputs previously followed source HEAD, and automatic snapshots could bypass normal
   hooks or include secrets/generated files. Inputs are pinned; guarded internal checkpoints
   preserve isolation without claiming delivery hooks passed. Direct delivery commits retain
   normal project hooks and explicit selected paths.

## Result

No known blocking finding remains. Native/live-account limitations are documented in the test
report and harness/runtime contracts. The requested delivery is one local commit; remote PR/MR
creation, merging, package installation and production changes are outside this run's authority.
