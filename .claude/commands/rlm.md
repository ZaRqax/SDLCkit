---
description: Launch the RLM recursive solver on a big task — decompose → delegate to fresh sub-solvers → aggregate (bounded depth/fanout/budget, read-only).
argument-hint: "<task too big for one pass>"
allowed-tools: Read, Grep, Glob, Bash, Task
---

Launch the **RLM recursive solver** (Recursive Language Models, arXiv:2512.24601) on:

**$ARGUMENTS**

This is a **utility**, not a pipeline phase. Use it when the task is too big for one pass — a huge
context or a broad sweep (audit all services for X, understand a whole subsystem, answer over a massive
log/spec/diff). It is **read-only**: it reads/analyzes and returns a synthesized answer; it does not
edit code (writes go through the isolated implementation coordinator).

> Runs under Claude Code as `/rlm <task>`. It is also a plain runbook — any agent (pi, Qwen, Crush,
> opencode) executes the same protocol by hand. Full reference: the **rlm-recursive** skill.

## How to run it

1. **Claude Code (genuine recursion):** run the bundled workflow —
   `Workflow({ name: "rlm", args: { task: "$ARGUMENTS", maxDepth: 3, fanout: 5 } })`
   (`.claude/workflows/rlm.js`). It spawns one fresh agent per node, parallel children, with the rails
   enforced in code. Read the synthesized result it returns and relay it.
2. **pi / opencode:** invoke the `rlm` subagent (`/run rlm "$ARGUMENTS"` / `task(rlm, "$ARGUMENTS")`);
   it delegates children with `/run rlm` / `task(rlm, …)` per the protocol.
3. **No nested-subagent harness (Qwen/Crush) or quick check:** run the protocol by hand —

   - **SIZE:** if `$ARGUMENTS` fits one focused pass, just answer it (recursion has overhead). Else:
   - **DECOMPOSE** into 2–5 **independent** subtasks, each over a snippet of the context.
   - **SOLVE** each subtask (recurse if still too big, down to max depth 3 / fanout 5 / budget).
   - **AGGREGATE** into one synthesized answer — reconcile, dedupe, cite sources (`file:line`/ticket/URL).

## Rails (always)
Max depth **3**, max fanout **5**, hard budget; **base case first** (never recurse on a one-pass task);
**independent** subtasks only; pass **snippets/references**, not the whole context; **read-only** —
no code edits inside recursion. English only. Return a synthesis, never a pile of sub-answers.
