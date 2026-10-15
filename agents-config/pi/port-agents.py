#!/usr/bin/env python3
"""Port the kit's canonical Claude subagents (.claude/agents/*.md) into pi-subagents format.

pi-subagents does NOT read .claude/agents/ — it discovers agents from .pi/agents/**/*.md (project)
or ~/.pi/agent/agents/**/*.md (user), with the SAME markdown+frontmatter shape but pi-specific keys.
Rather than duplicate the agent bodies (drift risk), generate the pi copies from the single source.

Usage:
  python3 port-agents.py [OUT_DIR]
    OUT_DIR defaults to ./agents (next to this script). setup.sh passes ~/.pi/agent/agents.

Frontmatter remap (Claude -> pi-subagents):
  name/description/skills : verbatim
  tools  : Read->read Write->write Edit->edit Bash->bash Grep->grep Glob->find ; mcp__atlassian->mcp:atlassian
  model  : opus->selfhosted/GLM-5.1 ; sonnet|haiku->selfhosted/Qwen3-Coder-Next ; inherit->omitted
  added  : systemPromptMode: append, inheritProjectContext: true, inheritSkills: true
           completionGuard: false  (for every agent EXCEPT the implementing 'engineer')
Body is copied verbatim. [INF] pi builtin tool names (grep/find) — verify with `pi`/`/tools`.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
SRC = os.path.join(ROOT, ".claude", "agents")
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "agents")

# Honor the pipeline toggle (config/pipeline.yaml) so a disabled agent is never generated for pi.
# Fail open: if the shared parser or the config is unavailable, port every agent.
sys.path.insert(0, os.path.join(ROOT, "scripts"))
try:
    import pipeline_config
    from role_library import claude_source

    DISABLED = set(pipeline_config.disabled_agents())
except ImportError:  # Legacy fallback only when the optional shared bridge is unavailable
    DISABLED = set()

TOOL_MAP = {
    "Read": "read", "Write": "write", "Edit": "edit", "Bash": "bash",
    "Grep": "grep", "Glob": "find", "mcp__atlassian": "mcp:atlassian",
}
MODEL_MAP = {}  # Model selection belongs to the active harness/profile.


def split_frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.DOTALL)
    if not m:
        return None, text
    return m.group(1), m.group(2)


def parse_fm(fm):
    """Tolerant parse for the kit's known frontmatter shape."""
    data, key, buf, lst = {}, None, [], None
    for line in fm.splitlines():
        top = re.match(r"^([A-Za-z_][\w-]*):\s?(.*)$", line)
        if top and not line.startswith(" "):
            if key == "description":
                data["description"] = " ".join(s.strip() for s in buf if s.strip())
            key, val = top.group(1), top.group(2).strip()
            buf, lst = [], None
            if key == "description":
                buf = [] if val in (">", "|", "") else [val]
            elif key == "skills":
                lst = []
                data["skills"] = lst
            else:
                data[key] = val
        elif key == "description":
            buf.append(line)
        elif lst is not None:
            item = re.match(r"^\s*-\s*(.+)$", line)
            if item:
                lst.append(item.group(1).strip())
    if key == "description":
        data["description"] = " ".join(s.strip() for s in buf if s.strip())
    return data


def remap_tools(raw):
    out = []
    for t in (raw or "").split(","):
        t = t.strip()
        if not t:
            continue
        out.append(TOOL_MAP.get(t, t.lower()))
    seen, dedup = set(), []
    for t in out:
        if t not in seen:
            seen.add(t)
            dedup.append(t)
    return dedup


def wrap(text, width=96, indent="  "):
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(indent + cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(indent + cur)
    return "\n".join(lines)


def port(path):
    name = os.path.splitext(os.path.basename(path))[0]
    fm_raw, body = split_frontmatter(claude_source(path))
    if fm_raw is None:
        return None
    fm = parse_fm(fm_raw)
    tools = remap_tools(fm.get("tools", ""))
    model = MODEL_MAP.get((fm.get("model") or "").strip())
    lines = ["---", f"name: {fm.get('name', name)}"]
    if fm.get("description"):
        lines.append("description: >")
        lines.append(wrap(fm["description"]))
    if tools:
        lines.append("tools: " + ", ".join(tools))
    if model:
        lines.append(f"model: {model}")
    lines.append("systemPromptMode: append")
    lines.append("inheritProjectContext: true")
    lines.append("inheritSkills: true")
    if name != "engineer":  # the implementing agent keeps the default completion guard
        lines.append("completionGuard: false")
    if fm.get("skills"):
        lines.append("skills:")
        lines += [f"  - {s}" for s in fm["skills"]]
    lines.append("---")
    return name, "\n".join(lines) + "\n" + body.lstrip("\n")


def main():
    if not os.path.isdir(SRC):
        sys.exit(f"source agents dir not found: {SRC}")
    os.makedirs(OUT, exist_ok=True)
    n, skipped = 0, 0
    for fn in sorted(os.listdir(SRC)):
        if not fn.endswith(".md"):
            continue
        if os.path.splitext(fn)[0] in DISABLED:  # pipeline toggle: agent off
            skipped += 1
            stale = os.path.join(OUT, fn)
            if os.path.isfile(stale):
                os.unlink(stale)  # OUT is the legacy generated snapshot directory.
            print(f"  skipped {fn} (disabled in role selection)")
            continue
        res = port(os.path.join(SRC, fn))
        if not res:
            continue
        name, text = res
        with open(os.path.join(OUT, f"{name}.md"), "w", encoding="utf-8") as f:
            f.write(text)
        print(f"  ported {name} -> {OUT}/{name}.md")
        n += 1
    print(f"ported {n} agents to pi-subagents format" + (f" ({skipped} disabled)" if skipped else ""))


if __name__ == "__main__":
    main()
