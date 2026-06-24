---
name: jira-flow
description: >
  Use to read a ticket's context, create/update/transition a story, add a worklog or comment, or
  write a Confluence page. Invoke for any Jira/Confluence work in the PROJ or TEAM projects, e.g.
  "what does PROJ-1234 ask for", "move the story to In Review", "log my time", "post the PR link on
  the ticket". Invoke with /jira-flow for the full reference.
compatibility:
  tools: [mcp__atlassian]
---

# jira-flow — read & update Jira / Confluence over the Atlassian MCP

This kit ships **sooperset/mcp-atlassian** (Docker). The default profile is **read-write via a
service account**, scoped to `JIRA_PROJECTS_FILTER=PROJ,TEAM`. Tool names are `mcp__atlassian__*`.

**Read-only profile.** If the deployment sets `ATLASSIAN_READ_ONLY=true`, every write tool
(`jira_create_issue`, `jira_update_issue`, `jira_transition_issue`, `jira_add_comment`,
`jira_add_worklog`, `confluence_create_page`) is disabled and not registered. If a write tool you
need is unavailable, **stop and say so** — do not fabricate a result. Reads always work.

Only PROJ and TEAM are in scope. Don't touch other projects.

## Reading context (do this before any implementation phase)

Read the ticket behind the work first — it is the spec input for the `/spec` phase.

```
# Fetch one issue, full fields (description, AC, status, links)
mcp__atlassian__jira_get_issue(issue_key="PROJ-1234")

# Find issues by JQL — keep it scoped to PROJ,TEAM
mcp__atlassian__jira_search(
  jql="project IN (PROJ, TEAM) AND assignee = currentUser() AND statusCategory != Done ORDER BY updated DESC",
  limit=20
)
```

Pull related Confluence design docs:

```
mcp__atlassian__confluence_search(query="Acme offer pricing design")
mcp__atlassian__confluence_get_page(page_id="123456789")
```

## Writing (read-write profile only)

```
# New story (parent ties it to an epic)
mcp__atlassian__jira_create_issue(
  project_key="PROJ", issue_type="Story",
  summary="Sync inventory on offer update",
  description="As a seller ...\n\nAcceptance criteria:\n- ...",
)

# Edit fields
mcp__atlassian__jira_update_issue(
  issue_key="PROJ-1234",
  fields={"summary": "Sync inventory on offer update (B2C)"},
)

# Comment / worklog
mcp__atlassian__jira_add_comment(issue_key="PROJ-1234", comment="Blocked on contracts-proto bump.")
mcp__atlassian__jira_add_worklog(issue_key="PROJ-1234", time_spent="2h", comment="Repo + mapper impl")

# Confluence page (write-up / runbook)
mcp__atlassian__confluence_create_page(
  space_key="PROJ", title="PROJ-1234 — inventory sync design",
  content="<h2>Context</h2>...",  # storage format / markdown per server config
)
```

## Worked example — at PR time, transition to In Review and post the PR link

Run this in the `/pr` phase, right after the PR is opened. Transition names are case-sensitive and
must match the board's workflow — discover them, don't guess.

```
# 1. Confirm the available transitions for this issue's current status
mcp__atlassian__jira_get_transitions(issue_key="PROJ-1234")
#   -> e.g. [{"id":"31","name":"In Review"}, {"id":"41","name":"Done"}]

# 2. Move the story to In Review (by name; the server resolves the id)
mcp__atlassian__jira_transition_issue(issue_key="PROJ-1234", transition="In Review")

# 3. Drop the PR link as a comment so reviewers find it from the ticket
mcp__atlassian__jira_add_comment(
  issue_key="PROJ-1234",
  comment="PR opened: https://github.com/acme/marketplace/pull/87",
)
```

If step 2 or 3 errors with "tool not available" / "read-only", report: "Atlassian MCP is in
read-only mode — I read PROJ-1234 but cannot transition it or comment. Do this manually, or enable
the read-write profile." Never claim the transition happened when it didn't.

## Rules

- **Scope JQL to `project IN (PROJ, TEAM)`** — never run an unbounded search.
- **Discover transitions with `jira_get_transitions` before `jira_transition_issue`** — names vary
  per board and per current status.
- **Verify before claim**: a write tool returning an error means it did not happen — say so.
- **Ask first** before creating or transitioning an issue if you are not sure the human wants it
  (per AGENTS.md §8 "Ask first").
- Match commit/branch conventions when you reference work on the ticket: branch
  `<type>/PROJ-1234-<desc>`, commit `<type>(PROJ-1234): <desc>`.
