# Weak-Model Playbook — why the kit is shaped this way, and how to keep authoring for it

> Maintainer/operator doc. Read this before adding or editing a skill, command, or agent. The kit
> targets **weak open models** (GLM-5.1, Qwen3-Coder-Next) running under pi/Qwen Code/Crush/opencode,
> while staying correct under Claude Code. Every shaping decision below exists to cancel a specific
> failure mode of those models. Author new components the same way, or you reintroduce the failure.

---

## The premise

A frontier model can be handed a terse "you know the conventions, ship it" doc and mostly succeed.
GLM-5.1 / Qwen3-Coder-Next **cannot**. They follow instructions shallowly, plan one step deep, and
confidently invent APIs. The kit does not ask them to be smarter — it removes the situations where
their weaknesses bite, and replaces "judgement" with **explicit steps, real examples, and tools that
make hallucination impossible.** When you author a new file, your job is the same: leave nothing to
the model's judgement that you can encode as a step.

---

## The six failure modes (name the enemy)

1. **Weak instruction-following.** A rule stated once, mid-document, gets dropped. The model attends
   to the top and the bottom of a file and skims the middle.
2. **Shallow planning.** Asked to "implement X", it edits the first file it thinks of and stops —
   no decomposition, no ordering, no "which files does this touch".
3. **API hallucination.** It writes `repo.GetProductBySKU(ctx, sku)` because that *sounds* right,
   never checking the method exists. Confidently. With correct-looking error wrapping.
4. **Partial edits.** Mid-file it emits `// ... rest unchanged` or re-writes a struct literal with
   half the fields, silently zeroing the rest (the team's #1 recurring bug — AGENTS.md §5).
5. **Premature done.** It says "Done!" with a failing build, a stub, a TODO, or three of seven
   tasks finished — because nothing forced it to check.
6. **Context rot.** Over a long task it forgets earlier decisions, re-reads whole files, blows the
   window, and starts contradicting its own plan.

---

## The five compensating levers (cite these by name in reviews)

### Lever 1 — Mandatory gated phases (kills shallow planning + premature done)
The pipeline `spec → clarify → plan → tasks → implement → test → review → pr` (AGENTS.md §2) forces
decomposition *before* code exists. Each phase reads the previous artifact and writes the next into
`specs/<TASK_ID>-<slug>/`. The `tasks.md` gate ("human approves before coding") means the model can't
skip from a vague idea to editing. The artifacts are external memory — the model re-reads `tasks.md`
instead of trusting its context. **A weak model with a written plan in front of it plans deep enough.**

### Lever 2 — Show-don't-tell worked examples (kills weak instruction-following + hallucination)
Every non-trivial rule in AGENTS.md carries ONE real, compilable Go example: the transport→service
call chain (§4), the table-driven testify test (§4), the `%w` error wrap (§4), the forbidden-vs-correct
partial struct (§5). Weak models pattern-match far better than they reason from prose. A rule with an
example is followed; a rule described in abstract is not. The example also pins the *exact* repo
shape (gci import order, error verbosity, mock setup) so the model copies instead of inventing.

### Lever 3 — Serena symbol tools + tool-layer validation (kills hallucination + context rot)
Serena (over `gopls`) is mandated over whole-file reads/edits (AGENTS.md §6). `find_symbol` /
`get_symbols_overview` make the model *look at the real signature* before calling it — a method it
can't find via the language server is a method it won't write. `find_referencing_symbols` before a
change supplies the impact analysis the model won't do on its own. Symbol-anchored edits
(`replace_symbol_body`, `insert_after_symbol`) sidestep fragile line/string edits, the usual source
of partial-edit corruption. context7 does the same for third-party APIs. And enforcement is **layered**
(KIT-DEV.md): prose is only context — the `.githooks/pre-commit` + CI catch what the model ignores.

### Lever 4 — Explicit Definition of Done + anti-elision + no-partial-structs (kills premature done + partial edits)
AGENTS.md §9 is a literal checklist the model must restate, ticked, before finishing — and §0 rule 5 forbids
declaring success otherwise. §5 bans partial domain structs and `// ...` elisions in *both* struct
literals and file writes ("emit the complete code region"). These convert "did I finish?" from a
judgement call into a mechanical check the weak model can actually perform. The DoD is restated at the
file tail so it lands in the model's attention window.

### Lever 5 — Pinned sampling + ask-for-help (kills thrashing + drift)
Sampling is pinned to each model's **official** recommended values in `agents-config/sampling-params.md`
(KIT-DEV.md) — Qwen3-Coder-Next and GLM both want `temperature 1.0 / top_p 0.95 / top_k 40`; off-spec
sampling (especially lowering temperature for Qwen3-Coder) *degrades* tool-calling, so the kit follows
the vendor settings rather than guessing. And AGENTS.md §0 rule 6 gives an explicit escape hatch:
ambiguous task, a test failing 2–3 times, or a change crossing service boundaries → **stop and ask one
question**, don't guess. A weak model left to thrash digs the hole deeper; a forced stop caps the damage.

---

## Authoring rules for new skills / commands / agents

Apply these whenever you add a kit file. They are the levers, operationalized.

1. **Be explicit; inline the recipe.** Never write "use Serena to find the symbol" — write the actual
   call sequence: `get_symbols_overview <file>` → `find_symbol <Name>` → `replace_symbol_body`. Weak
   models can't fill gaps. Spell out every tool call, in order, with the argument shape.
   ```text
   ❌  "Verify the proto message exists before mapping it."
   ✅  "Run: grep -rn 'GetProductResponse' gen/ — if it returns nothing, the field does NOT exist; stop and ask."
   ```
2. **Exactly ONE worked example, and make it real.** Pull it from this repo (Catalog/Marketplace/Users),
   reuse the shapes already in AGENTS.md (transport→service→repository, `%w` wrap, table-driven test).
   One concrete example beats three abstract bullets. Do not invent a repo API to make an example tidy —
   if you can't justify it from AGENTS.md, don't write it.
3. **Encode the conventions, every time.** Clean architecture (transport never calls a repository),
   NO partial structs, English-only code, generated code never hand-edited (regenerate with
   `task sqlc` / `task mocks` / `task gen`), conventional commits `<type>(<TASK_ID>): <desc>`, branch
   `<type>/<TASK_ID>-<desc>`, Definition of Done before "done". If your component touches one of these,
   restate it — don't assume the model read it in AGENTS.md.
4. **Keep files short — under 200 lines (agents ~60–100, commands ~30–60, skills ~40–90).** A weak
   model that overflows its window loses the middle. If a file wants to be longer, split detail into a
   `reference.md` sidecar (progressive disclosure) and keep the main file a runnable runbook.
5. **Head + tail placement.** Put the most important rule first AND restate it last — weak models
   attend to the top and bottom, skim the middle. AGENTS.md models this: §0 up top, the one-line
   reminder at the tail. Every agent body must open with the phase + DoD reminder and close with the
   handoff step.
6. **Write standalone runbooks.** Open agents can't auto-load skills or resolve cross-references. Each
   skill/command must read top-to-bottom as a complete procedure — name the phase it belongs to, read
   the prior artifact, write the next from its `templates/` file, and end by restating the gate/DoD.
7. **Don't rely on judgement you can encode.** Anywhere you're tempted to write "use your best
   judgement", convert it to a check (a grep, a DoD line, a stop-and-ask trigger). That conversion *is*
   the kit.

---

## The one-line operator reminder
Weak models follow steps, not vibes. Name the failure mode, pick the lever, encode it as an explicit
recipe with one real example, keep the file short, and repeat the rule at head and tail. If it needs
judgement, turn it into a check.
