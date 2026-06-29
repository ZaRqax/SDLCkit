#!/usr/bin/env python3
"""Port the kit's canonical Claude subagents, commands, and skills into Qwen Code format.

Qwen Code does NOT read .claude/{agents,commands,skills}. It discovers project agents from
.qwen/agents/*.md, commands from .qwen/commands/*.md, and skills from .qwen/skills/<name>/SKILL.md.
Qwen is the most Claude-compatible of the open harnesses — it accepts the Claude Code 2.1.168 agent
frontmatter (name/description/tools/model, plus permissionMode/maxTurns/color/mcpServers/hooks) — so
porting is mostly a faithful copy with three deliberate remaps. Rather than duplicate the bodies (drift
risk), generate the Qwen copies from the single source, exactly like agents-config/opencode/port-to-opencode.py.

Usage:
  python3 port-to-qwen.py [OUT_DIR]
    OUT_DIR defaults to ./.qwen (the project's Qwen config dir). setup.sh passes .qwen.
    Writes OUT_DIR/agents/<name>.md, OUT_DIR/commands/<name>.md, OUT_DIR/skills/<name>/SKILL.md, and
    prints each path written (one per line) so setup.sh can record them in its uninstall manifest.

Remaps (Claude -> Qwen), and why:
  AGENTS:
    name        : verbatim (Qwen reads `name` from frontmatter).
    description : verbatim (block scalar preserved).
    model       : remapped to a Qwen SELECTOR per role (MODEL_BY_AGENT) — never a hardcoded model id.
                  The source uses Claude names (opus/sonnet) to mean "strong model"; Qwen selectors are
                  `inherit` (the session's main/strong model) and `fast` (the configured fastModel).
                  Judgment-heavy roles keep `inherit`; mechanical / high-fanout roles use `fast`.
    tools       : NOT emitted for write-capable agents — omitting `tools` makes Qwen inherit the full
                  parent tool set INCLUDING all MCP servers (an explicit allowlist would drop MCP, since
                  Qwen only grants MCP tools named individually). Read-only agents instead get
                  `disallowedTools: [write_file, edit]` — they inherit every read tool and all MCP, but
                  cannot mutate files. This enforces read-only at the tool level without losing Serena.
    skills      : dropped from frontmatter (Qwen has no `skills` agent key yet — it is dropped at parse)
                  and noted in a body footer. The skills themselves ARE installed at .qwen/skills/, so
                  Qwen auto-loads them by description; the footer is just a pointer.
  COMMANDS:
    description    : verbatim.
    argument-hint  : dropped (not needed for Qwen custom commands).
    allowed-tools  : dropped (commands run under the invoking session's grants).
    body $1        : rewritten to $ARGUMENTS (Qwen interpolates $ARGUMENTS; $1 == the whole arg here).
  SKILLS:
    Copied verbatim (SKILL.md + any reference.md) — the format is identical.
"""
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
SRC_AGENTS = os.path.join(ROOT, ".claude", "agents")
SRC_COMMANDS = os.path.join(ROOT, ".claude", "commands")
SRC_SKILLS = os.path.join(ROOT, ".claude", "skills")
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, ".qwen")

# Honor the pipeline toggle (config/pipeline.yaml): never generate a disabled agent, nor a command
# whose only owning agent is disabled. Fail open if the parser/config is unavailable.
sys.path.insert(0, os.path.join(ROOT, "scripts"))
try:
    import pipeline_config

    DISABLED_AGENTS = set(pipeline_config.disabled_agents())
    DISABLED_COMMANDS = set(pipeline_config.disabled_commands())
except Exception:  # noqa: BLE001 — any import/parse failure must not break porting
    DISABLED_AGENTS, DISABLED_COMMANDS = set(), set()

# Per-role model selection (review §6.3). Qwen SELECTORS only — never a hardcoded model id:
#   inherit -> the session's main (strong) model;  fast -> the configured fastModel.
# Judgment-heavy roles keep the strong model; mechanical / high-fanout roles use the fast model.
# An agent not listed here defaults to `inherit`.
MODEL_BY_AGENT = {
    "planner": "inherit",          # spec + clarify — judgment
    "tech-designer": "inherit",    # plan + tasks — judgment
    "go-code-reviewer": "inherit", # review — judgment
    "devops-lead": "inherit",      # infra decisions — judgment
    "engineer": "fast",            # implementation — mechanical, high volume
    "qa-lead": "fast",             # test authoring + debug loop — high volume
    "rlm": "fast",                 # high-fanout recursive utility — cost-sensitive
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


def is_readonly(raw_tools):
    """True if the source agent grants neither Write nor Edit (a read-only specialist)."""
    toks = {t.strip() for t in (raw_tools or "").split(",")}
    return not (toks & {"Write", "Edit"})


def port_agent(path):
    name = os.path.splitext(os.path.basename(path))[0]
    with open(path, encoding="utf-8") as f:
        fm_raw, body = split_frontmatter(f.read())
    if fm_raw is None:
        return None
    fm = parse_fm(fm_raw)
    lines = ["---", f"name: {name}"]
    if fm.get("description"):
        lines.append("description: >")
        lines.append(wrap(fm["description"]))
    lines.append(f"model: {MODEL_BY_AGENT.get(name, 'inherit')}")
    if is_readonly(fm.get("tools", "")):
        # Read-only specialist: inherit every read tool + all MCP, but block file mutation.
        lines.append("disallowedTools:")
        lines.append("  - write_file")
        lines.append("  - edit")
    # Write-capable agents: omit `tools` entirely so they inherit the full tool set INCLUDING all MCP
    # servers (an explicit allowlist would silently drop MCP tools in Qwen).
    lines.append("---")
    out = "\n".join(lines) + "\n" + body.lstrip("\n")
    skills = fm.get("skills") or []
    if skills:
        out = out.rstrip() + (
            "\n\n---\n**Skills available:** "
            + ", ".join(skills)
            + ".\nEach is installed at `.qwen/skills/<name>/SKILL.md` and auto-loads when relevant;"
            " open it for the full runbook.\n"
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
    lines.append("---")
    # Qwen interpolates $ARGUMENTS, not positional $1 — rewrite standalone $1 tokens ($1 == whole arg).
    body = re.sub(r"\$1(?![0-9A-Za-z_])", "$ARGUMENTS", body)
    return name, "\n".join(lines) + "\n" + body.lstrip("\n")


def emit_md(src_dir, out_dir, porter, skip_names=frozenset()):
    if not os.path.isdir(src_dir):
        return []
    os.makedirs(out_dir, exist_ok=True)
    written = []
    for fn in sorted(os.listdir(src_dir)):
        if not fn.endswith(".md"):
            continue
        if os.path.splitext(fn)[0] in skip_names:  # pipeline toggle: agent/command off
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


def emit_skills(src_dir, out_dir):
    """Copy every skill dir verbatim (SKILL.md + reference.md + any other files). Skills are not
    pipeline-toggleable, so all of them are ported."""
    if not os.path.isdir(src_dir):
        return []
    written = []
    for name in sorted(os.listdir(src_dir)):
        sdir = os.path.join(src_dir, name)
        if not os.path.isdir(sdir):
            continue
        ddir = os.path.join(out_dir, name)
        os.makedirs(ddir, exist_ok=True)
        for fn in sorted(os.listdir(sdir)):
            src = os.path.join(sdir, fn)
            if not os.path.isfile(src):
                continue
            dst = os.path.join(ddir, fn)
            shutil.copyfile(src, dst)
            written.append(dst)
    return written


def main():
    written = []
    written += emit_md(SRC_AGENTS, os.path.join(OUT, "agents"), port_agent, DISABLED_AGENTS)
    written += emit_md(SRC_COMMANDS, os.path.join(OUT, "commands"), port_command, DISABLED_COMMANDS)
    written += emit_skills(SRC_SKILLS, os.path.join(OUT, "skills"))
    for p in written:
        print(p)
    if not written:
        sys.exit(f"no source agents/commands/skills found under {SRC_AGENTS} / {SRC_COMMANDS} / {SRC_SKILLS}")


if __name__ == "__main__":
    main()
