/**
 * pi-mcp-bridge — gives the pi coding agent (pi.dev) MCP support, which it lacks natively.
 *
 * It reads a Claude-Code-compatible `mcpServers` config (../mcp.json, ~/.pi/agent/mcp.json, or
 * <cwd>/.pi/mcp.json), connects to each server over stdio, discovers its tools, and registers each
 * one as a pi tool named `mcp_<server>_<tool>` (the naming proposed in pi-mono#563).
 *
 * Place this file at ~/.pi/agent/extensions/mcp-bridge/index.ts (or <project>/.pi/extensions/...),
 * run `npm install` next to it, and start pi. See ./README.md.
 *
 * DOCUMENTED (verified against pi docs/extensions.md, examples/extensions/*, README): the pi-side
 * shape — async default-export factory awaited before startup; pi.registerTool({name,label,
 * description,parameters,execute}); execute(toolCallId, params, signal, onUpdate, ctx); return
 * { content:[{type:"text",text}], details }; throw to flag an error; pi.on("session_shutdown", ...).
 * INFERRED (verify against your installed @modelcontextprotocol/sdk version): the MCP SDK calls
 * (Client, StdioClientTransport, connect, listTools, callTool) and result shapes.
 *
 * For a production-grade, token-efficient alternative (lazy spawn, a single proxy `mcp` tool,
 * caching, directTools promotion) install `pi-mcp-adapter` instead: `pi install npm:pi-mcp-adapter`.
 */

// ---- pi-side imports (DOCUMENTED) ----
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { readFile } from "node:fs/promises";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

// ---- MCP SDK imports (INFERRED — pin/verify the version) ----
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";

interface McpServerSpec {
  command: string;
  args?: string[];
  env?: Record<string, string>;
  type?: string; // "stdio" assumed; "http"/"sse" not handled by this minimal bridge
}

const HERE = dirname(fileURLToPath(import.meta.url));

/** Merge mcpServers from the bundled config, the global pi config, and the project config. */
async function loadServers(cwd: string): Promise<Record<string, McpServerSpec>> {
  const paths = [
    join(HERE, "..", "mcp.json"),
    join(homedir(), ".pi", "agent", "mcp.json"),
    join(cwd, ".pi", "mcp.json"),
    join(cwd, ".mcp.json"),
  ];
  const merged: Record<string, McpServerSpec> = {};
  for (const p of paths) {
    try {
      const json = JSON.parse(await readFile(p, "utf8"));
      Object.assign(merged, json.mcpServers ?? {});
    } catch {
      /* missing/invalid file is fine — skip it */
    }
  }
  return merged;
}

/** Expand ${VAR} / ${VAR:-default} in a string against process.env (matches the kit's .mcp.json). */
function expand(value: string): string {
  return value.replace(/\$\{([A-Z0-9_]+)(?::-([^}]*))?\}/gi, (_m, name, def) => process.env[name] ?? def ?? "");
}
function expandSpec(spec: McpServerSpec): McpServerSpec {
  return {
    ...spec,
    args: (spec.args ?? []).map(expand),
    env: Object.fromEntries(Object.entries(spec.env ?? {}).map(([k, v]) => [k, expand(String(v))])),
  };
}

// pi awaits an async default-export factory before the first turn, so tools exist up front.
export default async function (pi: ExtensionAPI) {
  const cwd = process.cwd();
  const servers = await loadServers(cwd);
  const clients: Client[] = [];

  for (const [serverName, rawSpec] of Object.entries(servers)) {
    const spec = expandSpec(rawSpec);
    if (spec.type && spec.type !== "stdio") {
      // This minimal bridge handles stdio only. Use pi-mcp-adapter for http/sse transports.
      continue;
    }
    try {
      // ---- INFERRED: connect + discover ----
      const transport = new StdioClientTransport({
        command: spec.command,
        args: spec.args ?? [],
        env: { ...(process.env as Record<string, string>), ...(spec.env ?? {}) },
      });
      const client = new Client({ name: "pi-mcp-bridge", version: "0.1.0" }, { capabilities: {} });
      await client.connect(transport);
      clients.push(client);

      const { tools } = await client.listTools(); // INFERRED shape: { tools: [{ name, description, inputSchema }] }

      for (const tool of tools) {
        // ---- DOCUMENTED: register each discovered MCP tool as a pi tool ----
        pi.registerTool({
          name: `mcp_${serverName}_${tool.name}`,
          label: `${serverName}: ${tool.name}`,
          description: tool.description ?? `MCP tool ${tool.name} from ${serverName}`,
          // MCP inputSchema is JSON-Schema-shaped, like TypeBox. Pass it through; if pi rejects it,
          // translate to Type.Object(...). Empty fallback for tools without a schema.
          parameters: (tool.inputSchema as unknown as ReturnType<typeof Type.Object>) ?? Type.Object({}),
          async execute(_toolCallId, params, signal) {
            // ---- INFERRED: invoke the MCP tool ----
            const result: any = await client.callTool({ name: tool.name, arguments: params as any }, undefined, {
              signal,
            });
            const content = (result.content ?? []).map((c: any) =>
              c?.type === "text" ? { type: "text", text: c.text } : { type: "text", text: JSON.stringify(c) },
            );
            if (result.isError) {
              // DOCUMENTED: throwing flags the tool call as an error to the LLM.
              throw new Error(content.map((c: any) => c.text).join("\n") || `MCP tool ${tool.name} failed`);
            }
            return { content, details: { server: serverName, tool: tool.name } };
          },
        });
      }
    } catch (err) {
      // Don't let one broken server kill the others. Surface it on stderr.
      console.error(`[pi-mcp-bridge] failed to start MCP server "${serverName}": ${(err as Error).message}`);
    }
  }

  // DOCUMENTED: clean up child processes on shutdown.
  pi.on("session_shutdown", async () => {
    for (const c of clients) await c.close().catch(() => {});
  });
}
