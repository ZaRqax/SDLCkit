#!/usr/bin/env python3
"""Legacy roster queries backed by strict YAML/JSON and neutral role toggles.

CLI contracts remain: names, enabled, disabled, disabled-commands, expected-count,
disabled-core, check, json. Missing legacy files retain historical fail-open
behavior; malformed files fail explicitly. New enablement filters generated
adapters and never renames canonical source files.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
CONFIG = os.environ.get("SDLC_PIPELINE_CONFIG", os.path.join(ROOT, "config", "pipeline.yaml"))


def load(path=None):
    """Read a strict legacy roster or schema-v1 neutral role configuration.

    The historical helpers and CLI remain stable. Missing legacy config returns
    an empty roster; malformed/unsupported YAML is an explicit validation error.
    New role toggles filter generated outputs and never park canonical sources.
    """
    from pathlib import Path
    sys.path.insert(0, ROOT)
    from sdlc.config import read_document
    selected = Path(path or CONFIG)
    if not selected.exists():
        return {}
    document = read_document(selected)
    if 'agents' in document:
        agents = document['agents']
    elif document.get('schema_version') == 1 and isinstance(document.get('roles'), dict):
        agents = {name: dict(values, role='specialist', commands=[], phases=[])
                  for name, values in document['roles'].items()}
    else:
        raise ValueError(f'unsupported pipeline configuration: {selected}')
    if not isinstance(agents, dict):
        raise ValueError('pipeline agents must be a mapping')
    for name, values in agents.items():
        if not isinstance(values, dict) or not isinstance(values.get('enabled'), bool):
            raise ValueError(f'{name}: enabled must be true or false')
    # The legacy roster stays authoritative for legacy outputs; native rendering
    # uses effective neutral roles independently. No canonical source is parked.
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
    try:
        sys.exit(main(sys.argv))
    except (ValueError, OSError) as exc:
        print(f'pipeline configuration error: {exc}', file=sys.stderr)
        sys.exit(1)
