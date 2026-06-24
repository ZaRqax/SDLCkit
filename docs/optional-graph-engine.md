# Optional: the spec↔code graph + drift engine

> **Status: opt-in add-on. NOT part of the lightweight core.** The kit ships **without** this engine
> by default. Day-to-day semantic navigation is already covered by **Serena** (gopls-backed symbol
> tools — see §6 of `AGENTS.md` and the `serena-first` skill). Enable this only if your team wants
> *spec-traceability* enforced mechanically on every commit, and accepts a heavier, Node-based,
> Claude-oriented toolchain. If you are not sure you need it, you don't — use Serena.

## What it is

A homegrown, **offline** engine (a lightweight, in-house spec↔code drift tool) that builds a graph linking
two worlds and reports where they have drifted apart:

- **Spec nodes** — `Feature`, `Story`, `AC` (acceptance criterion), `Task` — parsed from the Markdown
  artifacts the pipeline already writes under `specs/<TASK_ID>-<slug>/` (`spec.md`, `tasks.md`).
- **Code nodes** — `File`, `Class`/`Type`, `Function` — extracted with **tree-sitter** (Go grammar)
  so it is language-server-free, fast, and runs on a CI box with no DB.
- **Edges** — `implements` (Task→Function), `covers` (Test→Function), `traces-to` (AC→Task), built
  from explicit `PROJ-1234`-style references in code/test/spec plus heuristic name matching.

The graph is persisted in an **embedded store** (e.g. a single SQLite/Kùzu file under `.kit/`), so
there is nothing to host. It is a *complement* to Serena, not a replacement: Serena answers "where is
this symbol / who calls it" live; this engine answers "which AC has no code, which code has no spec".

## What it reports — drift findings

On commit (or on demand) it diffs the graph and emits findings, each tied to a node:

| Finding     | Meaning                                                            |
|-------------|-------------------------------------------------------------------|
| `no_code`   | An `AC`/`Task` in `specs/` has no `implements` edge to any Function. |
| `no_tests`  | A Function implementing a Task has no `covers` edge from a test.   |
| `no_spec`   | A Function/File maps to no spec node — code with no traceable why. |
| `drifted`   | Spec text and the linked code changed independently since last sync. |

Findings are **informational by default** — they guide the engineer toward the Definition of Done
(`AGENTS.md` §9), they do not invent code.

## How you would enable it (outline only — not shipped)

1. **Scripts live out of the core**, under `tools/graph-engine/` (Node + TypeScript). Nothing in
   `.mcp.json`, `.claude/`, or the Go services depends on it; deleting the folder restores the core.
   ```
   tools/graph-engine/
   ├── parse-specs.ts      # specs/**/*.md  → Feature/Story/AC/Task nodes
   ├── parse-code.ts       # tree-sitter Go → File/Class/Function nodes + edges
   ├── build-graph.ts      # upsert nodes/edges into .kit/graph.db (embedded)
   ├── drift.ts            # diff graph → findings (no_code|no_tests|no_spec|drifted)
   └── eval.ts             # append one trend row to .kit/eval.jsonl
   ```
2. **A pre-commit hook that NEVER blocks.** Wire it into the existing `.githooks/pre-commit`
   (the open-agent enforcement layer) as an *informational* step — it prints findings and always
   exits 0, so it never gets in a committer's way:
   ```sh
   # .githooks/pre-commit  (append; informational, non-blocking)
   if [ -d tools/graph-engine ]; then
     node tools/graph-engine/drift.ts --since HEAD --report \
       || true   # never block the commit on drift findings
   fi
   ```
   Real gating stays where it belongs: `task fmt` / `task lint` / `task test` and CI.
3. **An eval JSONL trend.** Each run appends one line to `.kit/eval.jsonl` so you can watch
   traceability move over time (CI can chart it, no service involved):
   ```jsonl
   {"ts":"2026-06-23T10:00:00Z","commit":"a1b2c3d","no_code":4,"no_tests":7,"no_spec":2,"drifted":1}
   ```

## Why it is opt-in, and why the core skips it

- **Heavier + different runtime.** It is Node/TypeScript with a tree-sitter dependency and an embedded
  graph store — a second toolchain beside the Go workspace. The core stays Go-only + a few MCP servers.
- **Claude-oriented.** The findings are most useful when an agent reads them and closes the gaps; the
  weaker open models we primarily target (GLM-5.1, Qwen3-Coder-Next) get more value from the explicit
  phases and Serena symbol tools than from a drift graph.
- **Serena already covers the daily need.** "Find this symbol, find its callers, edit by symbol"
  is Serena's job and it is mandated in the core. The graph engine only adds *spec*-side traceability,
  which most tasks get for free by following the phased pipeline and the Definition of Done.

**Bottom line:** treat this as a bolt-on for teams that want mechanical spec-coverage reporting.
The default kit experience — phases, Serena, `task lint`/`task test`, hooks, CI — ships complete
without it.
