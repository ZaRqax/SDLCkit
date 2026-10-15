# Requirement adapter contract

The executable implementation is `sdlc/integrations.py`. Prompt/local files require no accounts.
Every fetched document records kind, reference, revision/hash, retrieval time, title, body,
metadata and `trust: untrusted_evidence`. Work IDs are internal stable hashes of source identity;
upstream IDs remain external references. Source bodies never become commands or approval grants.

```bash
python3 scripts/sdlc.py intake 'Make retry requests idempotent' --source prompt \
  --criterion 'A repeated key does not create another payout' --delivery patch
python3 scripts/sdlc.py intake requirements/retry.md --root /path/to/project \
  --criterion 'A repeated key returns the original result' --output .sdlc/runs/retry/work-item.json
```

An empty acceptance list is explicitly recorded as an unresolved question, not inferred success.
PDF files use `pdftotext` when installed; missing tools produce an actionable failure, not an empty
document. File retrieval is confined to the selected root, rejects symlink escapes and secret
paths, and limits content to 2 MiB. URLs require an enabled `url` integration, public HTTPS, no
embedded credentials and no redirects. Configure `hosts` to limit destinations further.

GitHub Issues use the authenticated `gh issue view --json` interface; GitLab Issues use
`glab issue view --output json`. Neither provider is enabled by merely detecting a remote URL.
Search is optional; GitHub CLI search returns at most 20 references.

Jira, Confluence, Linear, Notion and custom systems use a configured MCP stdio server. This is an
actual bounded JSON-RPC client with initialize/initialized, tools/list and tools/call; server tools
must exist. HTTP MCP transports are not silently converted to stdio. Map provider-specific argument
names explicitly. Servers and their authentication are configured/authorized separately; installation
does not install or start them. Example workspace fragment:

```yaml
integrations:
  jira:
    enabled: true
    command: [existing-jira-mcp-server]
    env_from: {JIRA_API_TOKEN: JIRA_API_TOKEN}
    reference_pattern: 'TEAM-[0-9]+'
    tools:
      fetch:
        name: jira_get_issue
        argument_map: {ref: issue_key}
      search:
        name: jira_search
        argument_map: {query: jql}
```

The configured tool names are examples requiring verification against the installed server.
Do not copy tokens into YAML. `env_from` references existing environment variable names.
The read adapter exposes only `fetch`, `search`, and `fetch_related`; it cannot transition issues
or execute sampling/elicitation requests. Such server requests receive a capability error.
The server itself must be trusted: tool declarations do not sandbox an arbitrary executable.

`fetch` returns an object with `title`, `body` (or `description`), optional `url`, `revision`, and
external ID. Plain text content is accepted as a body. `fetch_related` returns a reference list or
`{references: [...]}`; retrieval is one level with an explicit limit of at most 20. Unsupported
capabilities fail explicitly. The default deadline is 30 seconds and maximum is 120 seconds;
messages are bounded and provider stderr is not copied into model context.

Sources: [GitHub issue CLI](https://cli.github.com/manual/gh_issue_view),
[GitLab issue CLI](https://docs.gitlab.com/cli/issue/view/),
[MCP stdio transport](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports).
