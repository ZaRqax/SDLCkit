---
name: rlm-recursive
description: >
  Use for a task too big for one pass — a huge context or a broad sweep (audit all services for X,
  understand a 50-file subsystem, answer a question over a massive log/spec, summarize a giant diff).
  Recursively decompose → delegate each independent piece to a fresh solver → aggregate, with hard
  depth/fanout/budget rails. Invoke with /rlm or the rlm subagent. Read-only by default.
---

# rlm-recursive — Recursive Language Model solver for the kit

Standalone runbook. Implements the **Recursive Language Model** pattern (Zhang, Kraska, Khattab,
*Recursive Language Models*, arXiv:2512.24601 — MIT CSAIL): treat a big task/context as an external
thing you **decompose and recursively sub-query yourself over**, instead of cramming it into one
prompt. A root solver splits the work into independent snippets, delegates each to a **fresh instance
of itself**, and aggregates — handling inputs far beyond a single context window.

**Use it for** read/analysis/decomposition at scale: cross-service audits, large-context Q&A,
understanding/summarizing a big subsystem or diff, fan-out research. **Do NOT use it** to make
parallel code edits — recursive uncoordinated writes corrupt state; that is what the spec→…→pr
pipeline (and worktrees) are for. RLM here is **read-only by default**.

## The protocol (every node runs this)

A node receives `(task, depth, [context-handle])`. `context-handle` is a pointer — a file, glob, dir,
ticket, or large blob — **kept as a reference, never pasted wholesale** (that is the whole point).

1. **SIZE — is this a base case?** Yes if the task fits one focused pass (small/atomic, single clear
   sub-goal) **or** `depth == 0` **or** the budget is nearly spent. → **solve directly** (read the
   snippet, produce a concise result) and return. Do not decompose.
2. **DECOMPOSE** — otherwise split into 2–N **independent** subtasks, each over a *snippet* of the
   context (one service, one file-group, one chunk, one question). Independent = solvable without each
   other's output. Dependent steps stay **inside one** subtask (don't split a sequential chain).
   If you can't cleanly decompose, treat it as a base case and solve directly.
3. **DELEGATE** — launch a **fresh rlm node per subtask** at `depth-1`, in parallel. Each child gets
   only its snippet + sub-question — not the parent's whole context.
4. **AGGREGATE** — synthesize the children's results into one answer for `task`: reconcile overlaps,
   dedupe, resolve contradictions, keep citations. **Never blindly concatenate.** Return the synthesis.

## Rails (non-negotiable — recursion without these blows up cost or never terminates)

- **Max depth** (default **3**): passed down, decremented each level; at `0` a node MUST solve, not split.
- **Max fanout** (default **5**) per node: more pieces → group them, don't spawn 50 children.
- **Budget**: stop decomposing and solve directly once the token/node budget runs low.
- **Base case first**: never recurse on something a single focused pass can answer — that is pure waste.
- **Independence**: only split into pieces that don't depend on each other's output.
- **Read-only by default**: nodes read/grep/analyze. Code edits inside recursion require explicit
  human authorization and a different tool (the engineer + worktrees), not rlm.

## How recursion actually runs, per harness (no hand-waving)

- **Claude Code:** use the bundled workflow — `Workflow({name: "rlm", args: {task, maxDepth, fanout}})`
  (`.claude/workflows/rlm.js`). It is **genuine bounded recursion**: a recursive function spawns one
  fresh `agent()` per node, parallel children, depth/fanout/budget enforced in code. This is the
  reliable engine because a plain `.claude/agents/*` subagent cannot itself spawn subagents.
- **pi:** the `rlm` subagent delegates with `/run rlm "<subtask>"` per child (pi-subagents). Keep depth
  shallow; pi has no automatic budget guard, so honor the rails by hand.
- **opencode:** the `rlm` subagent delegates via `task(rlm, "<subtask>")`. Same rails by hand.
- **Qwen / Crush:** no nested-subagent primitive — run this runbook by hand: write the decomposition
  as a checklist, solve each leaf in its own focused turn, then aggregate.

## Worked example

Task: *"Audit all ~15 Acme services for direct repository access from transport (clean-arch
violation, AGENTS.md §3)."* One pass can't hold 15 repos.

- **Depth 2, root:** can't fit it → DECOMPOSE by service into ≤5 groups (catalog+marketplace+users,
  search+indexer+importer, …). Fanout 5; each group is independent. DELEGATE each group at depth 1.
- **Depth 1, group node:** still several services → DECOMPOSE to one subtask per service, delegate at
  depth 0.
- **Depth 0, leaf (base case forced):** for `catalog`, `grep -rn` transport handlers for direct
  `repository.`/`repo.` calls that skip the service layer; return `file:line` findings (read-only).
- **Aggregate up:** group node merges its services' findings; root merges groups into one deduped
  report grouped by service. No service's context ever entered another's prompt.

## Rules

- **Decompose only what doesn't fit.** Small task → just answer it; recursion has overhead.
- **Snippets, not the whole context** — pass each child a reference/slice, never the parent's full input.
- **Synthesize, don't staple.** The parent's job is a coherent answer, not a pile of child outputs.
- **Obey the rails every time** — depth, fanout, budget, base-case, independence, read-only.
- **English only**; cite sources (`file:line`, ticket, URL) so the aggregate is verifiable.
