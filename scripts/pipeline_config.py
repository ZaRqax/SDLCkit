#!/usr/bin/env python3
"""Read config/pipeline.yaml — the kit's single source of truth for which agents are active.

The kit's only Python dependency is the stdlib, so this is a TINY tolerant parser for the fixed shape
of config/pipeline.yaml (see the header in that file), NOT a general YAML parser. It is imported by
both porters (agents-config/{pi,opencode}) and shelled out to by check-kit.sh / apply-pipeline.sh, so
the toggle is honored identically everywhere from one place.

If the config is missing or unreadable, every helper degrades to "all agents enabled" so the kit keeps
working — a deleted config never silently drops agents.

Library use:
    import pipeline_config as pc
    pc.load()                  # {name: {role, phases, commands, enabled, note}}
    pc.is_enabled("rlm")       # bool (True if unknown — fail open)
    pc.enabled_agents()        # sorted [name, ...]
    pc.disabled_agents()       # sorted [name, ...]
    pc.command_agent()         # {command: owning-agent}
    pc.disabled_commands()     # sorted [command, ...] whose ONLY owning agent is disabled

CLI (one value per line unless noted):
    python3 scripts/pipeline_config.py names              # every agent name in the roster
    python3 scripts/pipeline_config.py enabled            # enabled agent names
    python3 scripts/pipeline_config.py disabled           # disabled agent names
    python3 scripts/pipeline_config.py disabled-commands  # commands to skip (owner disabled)
    python3 scripts/pipeline_config.py expected-count      # number of enabled agents (single int)
    python3 scripts/pipeline_config.py disabled-core       # enabled=false agents whose role=core-phase
    python3 scripts/pipeline_config.py check               # validate; exit 1 on a structural error
    python3 scripts/pipeline_config.py json                # the whole parsed roster as JSON
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
CONFIG = os.environ.get("SDLC_PIPELINE_CONFIG", os.path.join(ROOT, "config", "pipeline.yaml"))


def _scalar(val):
    """Parse a YAML-subset scalar: bool, inline [list], quoted/bare string."""
    val = val.strip()
    if val in ("true", "True"):
        return True
    if val in ("false", "False"):
        return False
    if val.startswith("[") and val.endswith("]"):
        inner = val[1:-1].strip()
        if not inner:
            return []
        out = []
        for item in inner.split(","):
            item = item.strip().strip("'\"")
            if item:
                out.append(int(item) if item.lstrip("-").isdigit() else item)
        return out
    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
        return val[1:-1]
    return val


def load(path=None):
    """Return {agent_name: {attrs}}. Empty dict if the config is absent/unreadable (fail open)."""
    path = path or CONFIG
    agents, in_agents, cur = {}, False, None
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return {}
    for raw in lines:
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not line.startswith(" "):  # a top-level key like `agents:`
            in_agents = stripped.rstrip(":") == "agents"
            cur = None
            continue
        if not in_agents:
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent == 2 and stripped.endswith(":"):  # an agent name
            cur = stripped[:-1].strip()
            agents[cur] = {}
        elif indent >= 4 and cur is not None and ":" in stripped:
            key, _, val = stripped.partition(":")
            agents[cur][key.strip()] = _scalar(val)
    return agents


def is_enabled(name, roster=None):
    roster = roster if roster is not None else load()
    agent = roster.get(name)
    if agent is None:  # unknown agent → fail open (don't hide what the config doesn't mention)
        return True
    return bool(agent.get("enabled", True))


def enabled_agents(roster=None):
    roster = roster if roster is not None else load()
    return sorted(n for n, a in roster.items() if bool(a.get("enabled", True)))


def disabled_agents(roster=None):
    roster = roster if roster is not None else load()
    return sorted(n for n, a in roster.items() if not bool(a.get("enabled", True)))


def command_agent(roster=None):
    """{command: owning-agent}. If two agents claim a command, last one wins (shouldn't happen)."""
    roster = roster if roster is not None else load()
    mapping = {}
    for name, a in roster.items():
        for cmd in a.get("commands", []) or []:
            mapping[cmd] = name
    return mapping


def disabled_commands(roster=None):
    """Commands whose every owning agent is disabled — safe for a porter to skip."""
    roster = roster if roster is not None else load()
    by_cmd = {}
    for name, a in roster.items():
        for cmd in a.get("commands", []) or []:
            by_cmd.setdefault(cmd, []).append(name)
    return sorted(c for c, owners in by_cmd.items() if all(not is_enabled(o, roster) for o in owners))


def disabled_core(roster=None):
    roster = roster if roster is not None else load()
    return sorted(
        n for n, a in roster.items()
        if not bool(a.get("enabled", True)) and a.get("role") == "core-phase"
    )


def _check(roster):
    errors, warnings = [], []
    if not roster:
        errors.append(f"no agents parsed from {CONFIG} (missing or malformed)")
        return errors, warnings
    for name, a in roster.items():
        if "enabled" not in a:
            errors.append(f"{name}: missing `enabled`")
        if "role" not in a:
            errors.append(f"{name}: missing `role`")
        elif a["role"] not in ("core-phase", "specialist", "utility"):
            errors.append(f"{name}: invalid role {a['role']!r}")
    for name in disabled_core(roster):
        warnings.append(f"{name}: a core-phase agent is DISABLED — phase(s) "
                        f"{roster[name].get('phases')} have no agent; run its command by hand")
    return errors, warnings


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "json"
    roster = load()
    if cmd == "names":
        print("\n".join(sorted(roster)))
    elif cmd == "enabled":
        print("\n".join(enabled_agents(roster)))
    elif cmd == "disabled":
        print("\n".join(disabled_agents(roster)))
    elif cmd == "disabled-commands":
        print("\n".join(disabled_commands(roster)))
    elif cmd == "expected-count":
        print(len(enabled_agents(roster)))
    elif cmd == "disabled-core":
        print("\n".join(disabled_core(roster)))
    elif cmd == "check":
        errors, warnings = _check(roster)
        for w in warnings:
            print(f"warning: {w}", file=sys.stderr)
        for e in errors:
            print(f"error: {e}", file=sys.stderr)
        return 1 if errors else 0
    elif cmd == "json":
        print(json.dumps(roster, indent=2, sort_keys=True))
    else:
        print(f"unknown query: {cmd}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
