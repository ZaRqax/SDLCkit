---
name: serena-first
description: Optional semantic navigation when a configured Serena server helps
---

# serena-first

This is an opt-in capability for repositories indexed by Serena. It is useful for symbol navigation and anchored changes, but is never a prerequisite for reading or editing code. If unavailable, use grep, LSP or scoped file reads and report material capability gaps.

When enabled, use get_symbols_overview to map a file, find_symbol for the enclosing definition and find_referencing_symbols before changing a signature. Use replace_symbol_body/insert_after_symbol/rename_symbol when they fit, then inspect the complete changed region and run target-project checks. Read non-symbol files directly. Never hand-edit generated outputs; change their inputs.

Example: before changing a method signature, locate it and its callers with Serena, make the complete symbol edit, update callers and execute the repository's relevant tests. If indexing is incomplete, inspect actual generated signatures or source with available tools; do not invent an API or expose credential values to repair indexing.
