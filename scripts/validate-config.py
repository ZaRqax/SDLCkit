#!/usr/bin/env python3
"""Validate an effective workspace and show provenance without writing files."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sdlc.config import explain_config


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', nargs='?')
    parser.add_argument('--project')
    parser.add_argument('--explain', action='store_true')
    args = parser.parse_args(argv)
    try:
        report = explain_config(args.path, args.project)
    except (ValueError, OSError) as exc:
        parser.exit(1, f'configuration error: {exc}\n')
    print(json.dumps(report if args.explain else report['effective'], indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
