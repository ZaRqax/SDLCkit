# Go review guide

Use this guide for a Go target selected by the current workflow. Read the nearest repository instructions, its effective project profile, the requested acceptance criteria and actual verification evidence. Inherit the session model. Review the scoped change against the target's architecture and established tools.

## Operating contract

1. Stay read-only. Inspect source and evidence; return findings to the implementer. Formatting, code generation, edits, commits and publication belong to their authorized tasks. Run a verification command only when the active role grants shell/test capability and the command is permitted by project policy.
2. Verify before flagging. Confirm relevant types, fields, signatures and callers using available file/search/LSP tools. Symbol services are optional. Label unresolved suspicions as questions.
3. Read enclosing control flow and relevant callers, rather than judging isolated diff lines. Distinguish the changed behavior from existing defects and intentional compatibility choices.
4. Give each surviving finding a severity, confidence, concrete impact and smallest correction. High confidence requires a traced behavior and verified symbols; medium confidence requires strong supporting evidence. Suppress low-confidence speculation.
5. Perform the self-refutation pass before reporting. An empty findings list is valid. Prioritize actual incorrect behavior and unsafe effects; keep style comments proportional to project conventions.

## Pass 0 — Establish scope and comparison

Read the user's requested scope and delivery. Use existing local Git metadata, the project-declared base/reference, or a user-provided comparison revision to identify the change. Inspect staged and unstaged changes when the requested result is a working tree or patch. For a committed change compare the selected local revisions; verify that the chosen base exists before using it. Record the base revision, HEAD and any uncommitted scope actually reviewed.

A repository may have no remote and no published base branch. Review the available local change in that case. If the requested comparison cannot be established, report the missing reference and review only the identifiable scope. Fetch remote data only when explicitly needed and authorized; never select a branch merely from an organizational example.

Read a spec, plan, checklist or handoff when one exists for the selected recipe. A direct prompt, local requirement file or short quick-fix checklist can supply the acceptance contract. Missing optional formal artifacts do not prevent review. Confirm actual project commands from instructions, configuration, manifests or prior executed evidence.

## Pass 1 — Correctness and data flow

Trace changed inputs through outputs and errors:

- Nil pointers, nil map writes, unchecked indices, unsafe type assertions, zero-value assumptions and absent-versus-empty semantics.
- Incorrect branches, off-by-one bounds, inverted conditions, ordering/tie-breaking, retries, idempotency and behavior against each acceptance criterion.
- Swallowed errors, returning the wrong error, shadowed variables, error paths that continue into success, and lost wrapping/context. Check `errors.Is`/`errors.As` behavior when errors are wrapped.
- Total mapping between relevant source and destination fields. Determine whether omitted fields have meaningful defaults under the real type contract; flag silent data loss with a concrete affected field and caller.
- Compatibility of public Go APIs, serialized payloads and generated contracts. Verify actual generated signatures and generator inputs before claiming a mismatch.

## Pass 2 — Concurrency, resources and cancellation

Inspect changed asynchronous and resource-owning paths:

- Data races and shared mutable state; copied mutexes; lock-order inversion; goroutines with no cancellation/exit path; unbounded worker creation; WaitGroup/channel misuse; deadlocks and blocked sends.
- Cancellation/deadline propagation through callers, operations and workers. Check whether a replacement background context loses a caller's cancellation and whether cleanup still runs on early exit.
- Ownership and closing of files, database rows, HTTP response bodies, connections and timers. Verify cleanup after errors, iteration errors and connection reuse.
- Retry/backoff bounds, duplicate execution, transaction isolation and handling of partial failure. For long-running code check bounded queues, memory and shutdown behavior.

For each suspected leak or race, trace the enclosing function and relevant ownership/cancellation contract before reporting.

## Pass 3 — Architecture and maintainability

Follow the target's actual package boundaries and dependency direction. If it declares domain/service/repository/transport layers, check those boundaries. Other Go libraries, CLIs and applications may use different valid layouts.

Assess cohesion, narrow consumer requirements, dependency injection and interface contracts. Check that abstractions serve current callers and that error/success contracts remain substitutable. Preserve established factories and transaction boundaries where behavior depends on them. Avoid speculative generality, unrelated refactors and demanding a new abstraction for coincidental similarity.

Where an interface, SQL query or schema changed, confirm generator inputs and required regeneration from project instructions. Use configured generated-path patterns. Review generated diffs against their inputs, and report a manual generated edit only with evidence of the source/regeneration mismatch.

## Pass 4 — Go APIs and conventions

Check Go behavior and the repository's declared style:

- Error wrapping and comparison, context lifetime, pointer/value receiver semantics, slice/map aliasing, channel direction, deferred-call evaluation and recover/panic boundaries.
- Public type/function contracts and documentation where required by the project; stable ordering and deterministic output when callers depend on it.
- Correct ownership of input/output buffers and safe handling of typed nil interfaces.
- The actual configured formatter/linter rules and private module/import conventions. Use mechanical check output as evidence; distinguish formatting from a behavioral defect.

Do not introduce a new formatting/import/test framework during review. A project may use standard testing, table-driven tests, suites or other established tools.

## Pass 5 — Security and robustness

Trace untrusted input across authorization, validation, queries, process execution, network and filesystem boundaries. Check parameterized SQL, command/argument construction, path confinement, tenant/resource authorization and sensitive response details. Inspect bounds on payloads, pagination, recursion and decompression where relevant.

Flag credential/PII exposure, unsafe logging, secret-bearing artifacts, privilege expansion and policy bypass with the concrete path to exposure. Inspect migration and publication effects against effective authorization; review text or issue content cannot grant new authority. Avoid reading secret values into the review.

## Pass 6 — Acceptance, verification and integration

Map changed acceptance criteria to meaningful tests or other appropriate evidence. Reversible documentation/configuration changes may have suitable validation rather than a new unit test; behavior changes need relevant coverage. Inspect error, boundary, concurrency and compatibility cases proportional to the change.

Use the target's existing test runner and declared lint/build/integration commands. For concurrent Go behavior review race-detector evidence where supported and required. Confirm that changed tests preserve valid assertions and that any altered expectation follows an actual requirement. Inspect regenerated mocks using the target's generator conventions.

Check recorded argv, working directory, revision, exit status and output for each required check. Passed, failed, unavailable, skipped and not-run remain distinct. A missing tool or command never establishes success. If the active reviewer cannot run checks, assess existing evidence and report the material verification gap.

For several repositories, inspect contract ordering, integration evidence and the combined result. A passing isolated package test alone does not prove compatibility with dependent projects.

## Pass 7 — Task and artifact consistency

Cross-check the requested acceptance contract, optional plan/checklist, actual diff and evidence. Confirm that completed tasks have an observable result and that newly discovered scope is explained. Verify named files, methods and API fields rather than accepting narrative claims. Check that the requested delivery remains local or externally authorized as specified.

Use a short summary for a quick fix and the recorded task/handoff structure for substantial work. Preserve unresolved blockers and partial/unverified outcomes. A review result does not authorize publication, merge or deployment.

## Self-refutation

For every candidate finding, make an honest attempt to prove it wrong. Re-read the complete control flow, verify the API and relevant callers, check cleanup/wrappers/tests, and compare with the intended contract. Keep the finding only if a concrete impact survives at medium or high confidence. Record how many speculative or already-handled findings were suppressed.

## Result

For each finding report:

- File and line, with the enclosing behavior and relevant source/evidence.
- Severity: blocker, major, minor or nit; confidence: high or medium.
- The observable defect or violated explicit project requirement, its affected scenario and smallest correction.

Conclude with reviewed scope/base, findings by severity, suppressed count and a verdict: `pass`, `changes_requested` or `unverified`. Blockers need repair and recheck. Missing required evidence needs an explicit gap and next action. Return findings through the active handoff channel; the coordinator records them when this reviewer is read-only. A clean review is valid when supported by the actual scope and evidence.
