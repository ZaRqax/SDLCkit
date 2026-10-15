#!/usr/bin/env python3
"""Preview or migrate a legacy pipeline roster without changing canonical agents."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sdlc.config import read_document

MAPPING = {'planner': 'analyst', 'tech-designer': 'architect', 'engineer': 'implementer',
           'qa-lead': 'verifier', 'go-code-reviewer': 'go-reviewer', 'devops-lead': 'devops-reviewer', 'rlm': 'rlm'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', nargs='?', default='config/pipeline.yaml')
    parser.add_argument('--output')
    args = parser.parse_args(argv)
    try:
        source = read_document(args.source)
        if not isinstance(source.get('agents'), dict):
            raise ValueError('legacy configuration must contain an agents mapping')
        roles = {MAPPING.get(name, name): {'enabled': bool(values.get('enabled', True))}
                 for name, values in source['agents'].items()}
        result = {'schema_version': 1, 'roles': roles}
        text = json.dumps(result, indent=2, sort_keys=True) + '\n'
        if args.output:
            # Never silently overwrite a user-maintained role configuration.
            with open(args.output, 'x', encoding='utf-8') as output:
                output.write(text)
        else:
            print(text, end='')
    except (OSError, ValueError) as exc:
        parser.exit(1, f'migration error: {exc}\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
