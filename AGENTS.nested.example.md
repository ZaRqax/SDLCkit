# Project instructions — example

Preserve this repository's existing architecture and conventions. Add concrete project guidance here; this example does not impose a language, tracker, branch model or delivery provider.

- Project ID / ownership: <id and boundaries>
- Verified commands: <format, lint, test, build, generators>
- Generated paths: <patterns and how to regenerate>
- Architecture/contracts: <actual layers and compatibility requirements>
- Base branch and naming: <repository policy>
- Required checks/review: <gates proportional to risk>
- Delivery: <default local artifact and allowed publishers>
- Policy: external writes require explicit scoped authorization; destructive actions, secret exposure, auto-merge and production deploy are forbidden.

Mirror executable commands/patterns in `.sdlc/project.yaml` or `.json` when using automation. Never store credentials in instructions or configuration. Optional Go conventions live in the kit's `profiles/go/`.
