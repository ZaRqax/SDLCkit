#!/usr/bin/env python3
"""Port the kit's canonical Claude subagents and commands into opencode format.

opencode does NOT read .claude/agents or .claude/commands. It discovers agents from
.opencode/agent/**/*.md and commands from .opencode/command/**/*.md (project scope), using the
SAME markdown+frontmatter shape but opencode-specific keys. Rather than duplicate the bodies (drift
risk), generate the opencode copies from the single source — exactly like agents-config/pi/port-agents.py
does for pi.

Usage:
  python3 port-to-opencode.py [OUT_DIR]
    OUT_DIR defaults to ./.opencode (next to the project root). setup.sh passes .opencode.
    Writes OUT_DIR/agent/<name>.md and OUT_DIR/command/<name>.md, and prints each path written
    (one per line) so setup.sh can record them in its uninstall manifest.

Frontmatter remap (Claude -> opencode):
  AGENTS:
    name        : dropped (opencode derives the agent name from the filename)
    description : verbatim
    mode        : subagent  (all kit specialists are sub-agents; the primary agent stays default)
    model       : dropped   (inherit the default model from opencode.json — never hardcode a model id)
    tools       : Read/Write/Edit/Bash/Grep/Glob -> opencode tool object (read/write/edit/bash/grep/glob);
                  capabilities the agent is NOT granted (write/edit/bash) are set false for parity.
    skills      : dropped from frontmatter (opencode has no native key) and appended to the body as a
                  "read the runbook" footer, since opencode won't auto-load .claude/skills.
  COMMANDS:
    description    : verbatim
    argument-hint  : dropped (opencode has no equivalent)
    allowed-tools  : dropped (commands run under their agent's tool grants)
    agent          : added — pins each phase command to its specialist subagent
    body $1        : rewritten to $ARGUMENTS (opencode interpolates $ARGUMENTS, not positional $1)
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
SRC_AGENTS = os.path.join(ROOT, ".claude", "agents")
SRC_COMMANDS = os.path.join(ROOT, ".claude", "commands")
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, ".opencode")

# Honor the pipeline toggle (config/pipeline.yaml): never generate a disabled agent, nor a command
# whose only owning agent is disabled. Fail open if the parser/config is unavailable.
sys.path.insert(0, os.path.join(ROOT, "scripts"))
try:
    import pipeline_config
    from role_library import claude_source

    DISABLED_AGENTS = set(pipeline_config.disabled_agents())
    DISABLED_COMMANDS = set(pipeline_config.disabled_commands())
except ImportError:  # Legacy fallback only when the optional shared bridge is unavailable
    DISABLED_AGENTS, DISABLED_COMMANDS = set(), set()

# Claude tool name -> opencode tool key.
CAP = {"Read": "read", "Write": "write", "Edit": "edit", "Bash": "bash", "Grep": "grep", "Glob": "glob"}
# Which subagent each phase command runs under.
COMMAND_AGENT = {
    "spec": "planner", "clarify": "planner",
    "plan": "tech-designer", "tasks": "tech-designer",
    "implement": "engineer", "test": "qa-lead",
    "review": "reviewer", "pr": "engineer", "deliver": "delivery",
    "rlm": "rlm",  # utility recursive solver (not a pipeline phase)
}


def split_frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.DOTALL)
    if not m:
        return None, text
    return m.group(1), m.group(2)


def parse_fm(fm):
    """Tolerant parse for the kit's known frontmatter shape (block scalars + simple lists)."""
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


def tool_grants(raw):
    """Return an ordered list of (opencode_tool_key, bool) for the agent's tool object."""
    granted = set()
    for t in (raw or "").split(","):
        t = t.strip()
        if t in CAP:
            granted.add(CAP[t])
    rows = []
    for k in ("read", "grep", "glob", "bash", "write", "edit"):
        if k in granted:
            rows.append((k, True))
    for k in ("write", "edit", "bash"):  # deny capabilities not granted, for parity
        if k not in granted:
            rows.append((k, False))
    # de-dup keeping first occurrence
    seen, out = set(), []
    for k, v in rows:
        if k not in seen:
            seen.add(k)
            out.append((k, v))
    return out


def port_agent(path):
    name = os.path.splitext(os.path.basename(path))[0]
    fm_raw, body = split_frontmatter(claude_source(path))
    if fm_raw is None:
        return None
    fm = parse_fm(fm_raw)
    lines = ["---"]
    if fm.get("description"):
        lines.append("description: >")
        lines.append(wrap(fm["description"]))
    lines.append("mode: subagent")
    grants = tool_grants(fm.get("tools", ""))
    if grants:
        lines.append("tools:")
        lines += [f"  {k}: {'true' if v else 'false'}" for k, v in grants]
    lines.append("---")
    out = "\n".join(lines) + "\n" + body.lstrip("\n")
    skills = fm.get("skills") or []
    if skills:
        out = out.rstrip() + (
            "\n\n---\n**Skills — read the runbook before acting:** "
            + ", ".join(skills)
            + ".\nEach lives at `.claude/skills/<name>/SKILL.md`; opencode does not auto-load them, so"
            " open and follow the relevant one.\n"
        )
    return name, out


def port_command(path):
    name = os.path.splitext(os.path.basename(path))[0]
    with open(path, encoding="utf-8") as f:
        fm_raw, body = split_frontmatter(f.read())
    fm = parse_fm(fm_raw) if fm_raw is not None else {}
    lines = ["---"]
    if fm.get("description"):
        lines.append(f"description: {fm['description']}")
    if name in COMMAND_AGENT:
        lines.append(f"agent: {COMMAND_AGENT[name]}")
    lines.append("---")
    # opencode interpolates $ARGUMENTS, not positional $1 — rewrite standalone $1 tokens.
    body = re.sub(r"\$1(?![0-9A-Za-z_])", "$ARGUMENTS", body)
    return name, "\n".join(lines) + "\n" + body.lstrip("\n")


def emit(src_dir, out_dir, porter, skip_names=frozenset()):
    if not os.path.isdir(src_dir):
        return []
    os.makedirs(out_dir, exist_ok=True)
    written = []
    for fn in sorted(os.listdir(src_dir)):
        if not fn.endswith(".md"):
            continue
        if os.path.splitext(fn)[0] in skip_names:
            stale = os.path.join(out_dir, fn)
            if os.path.isfile(stale):
                os.unlink(stale)  # Legacy output directories contain generated files only.
            continue
        res = porter(os.path.join(src_dir, fn))
        if not res:
            continue
        name, text = res
        dst = os.path.join(out_dir, f"{name}.md")
        with open(dst, "w", encoding="utf-8") as f:
            f.write(text)
        written.append(dst)
    return written


def main():
    written = []
    written += emit(SRC_AGENTS, os.path.join(OUT, "agent"), port_agent, DISABLED_AGENTS)
    written += emit(SRC_COMMANDS, os.path.join(OUT, "command"), port_command, DISABLED_COMMANDS)
    for p in written:
        print(p)
    if not written:
        sys.exit(f"no source agents/commands found under {SRC_AGENTS} / {SRC_COMMANDS}")


if __name__ == "__main__":
    main()
