# pi-mcp-bridge (FALLBACK)

> **This bridge is the documented FALLBACK.** The kit's default MCP path for pi is the
> **`pi-mcp-adapter`** package (declared in `agents-config/pi/settings.json` → `packages[]`). Use this
> hand-rolled bridge only when the adapter is unavailable (offline, npm registry blocked, an adapter
> bug). **Never run both at once** — they double-register tools. Both read the same `mcp.json`.

pi (pi.dev) has **no native MCP** — by design ("build CLI tools with READMEs, or build an extension
that adds MCP support"). This extension adds it: it reads a Claude-Code-style `mcpServers` config,
connects to each server over **stdio**, and registers every discovered MCP tool as a pi tool named
`mcp_<server>_<tool>`. That's how pi gets Serena, Atlassian, context7, etc.

## When to use the fallback
1. Remove `"npm:pi-mcp-adapter"` from `~/.pi/agent/settings.json` (keep only one MCP layer active).
2. `pi config` → enable the `mcp-bridge` extension.
3. `npm install` in `~/.pi/agent/extensions/mcp-bridge/`.
4. `/reload`. Verify with `/tools` (look for `mcp_serena_find_symbol`).

## Install

```bash
# 1. Put the extension where pi auto-discovers it (global):
mkdir -p ~/.pi/agent/extensions/mcp-bridge
cp src/index.ts ~/.pi/agent/extensions/mcp-bridge/index.ts
cp ../mcp.json   ~/.pi/agent/mcp.json        # the mcpServers config

# 2. Install its one runtime dep next to the extension:
cp package.json ~/.pi/agent/extensions/mcp-bridge/package.json
( cd ~/.pi/agent/extensions/mcp-bridge && npm install )

# 3. Export the kit's env (so ${VAR} in mcp.json resolves), then run pi:
set -a; source /path/to/sdlc-kit/.env; set +a
pi --model selfhosted/Qwen3-Coder-Next       # or selfhosted/GLM-5.1
```

pi loads TypeScript directly (via jiti) — no build step. Tools appear immediately;
`/reload` re-reads after edits. Confirm with `/tools` (you should see `mcp_serena_find_symbol`, etc.).

Per-project instead of global: drop `index.ts` in `<project>/.pi/extensions/mcp-bridge/` and the
config in `<project>/.pi/mcp.json`. Or load ad-hoc: `pi -e ~/.pi/agent/extensions/mcp-bridge/index.ts`.

## What's verified vs inferred

- **Documented (matches pi docs):** the extension shape — an async default-export factory that pi
  awaits before the first turn; `pi.registerTool({ name, label, description, parameters, execute })`;
  `execute(toolCallId, params, signal, onUpdate, ctx)`; returning `{ content: [{type:"text",text}],
  details }`; throwing to flag an error; `pi.on("session_shutdown", …)`; TypeBox for `parameters`.
- **Inferred (verify against your `@modelcontextprotocol/sdk` version):** the MCP SDK calls
  (`Client`, `StdioClientTransport`, `connect`, `listTools`, `callTool`) and result shapes, and that
  pi accepts a raw JSON-Schema object as `parameters` (translate `inputSchema` → `Type.Object(...)`
  if it doesn't). Only **stdio** transport is handled here (http/sse are skipped).

## Default (what the kit actually uses)

The kit ships **`pi-mcp-adapter`** as the default (lazy server spawning, a single token-efficient
`mcp()` proxy instead of registering every tool schema, disk caching, `directTools` promotion).
`setup.sh pi` installs it and points it at `~/.pi/agent/mcp.json` — no `/mcp setup` needed. This
hand-rolled bridge exists only as the offline fallback described at the top.

## Tracking

Official MCP-example work: https://github.com/badlogic/pi-mono/issues/563 — when pi ships first-class
MCP, prefer that and retire this bridge.
