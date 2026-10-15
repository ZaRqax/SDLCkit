# Optional Go profile

Select `--profile go` only for repositories that use these conventions. The installer discovers actual commands; generic Go defaults fill only missing commands; existing project commands take precedence. No default Go toolchain, private module host, Jira project or infrastructure credentials are required.

`AGENTS.md` preserves the v1 Acme example for migration/reference. It is **not** imported by the universal contract. Adapt it before copying into a project. `reviewer.md` provides the active generic Go passes and self-refutation technique, deriving base revisions, commands and acceptance evidence from the actual target. The historical organization-specific reviewer is preserved separately at `profiles/acme-go/reviewer.md` and is never installed by the generic Go profile. `go-layers.md` is a profile rule, never a universal Python/TypeScript rule. Legacy `.claude/skills/go-grpc-handler`, `sqlc-migration` and `testify-suite` remain available on demand.
