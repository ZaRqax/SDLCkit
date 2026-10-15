"""SDLCkit local CLI; all entry points delegate to the same library."""

import argparse
import importlib
import sys



def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    commands = {
        "intake": "sdlc.integrations", "deliver": "sdlc.delivery", "runtime": "sdlc.runtime_cli",
        "discover": "sdlc.discovery", "setup": "sdlc.installer", "doctor": "sdlc.installer",
        "config": "sdlc.config",
    }
    if not argv or argv[0] in {"--help", "-h"}:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("command", choices=commands, nargs="?", help="use COMMAND --help for detailed options")
        parser.print_help()
        return 0
    if argv[0] not in commands:
        raise SystemExit("unknown SDLCkit command; use --help")
    name = argv.pop(0)
    if name == "doctor":
        argv.insert(0, "--doctor")
    return importlib.import_module(commands[name]).main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
