#!/usr/bin/env python3
"""Regenerate compatibility Claude role bridges without changing role enablement."""
import argparse
from role_library import ALIASES, ROOT, claude_source


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    names = set(ALIASES) | {p.stem for p in (ROOT / 'roles').glob('*.md')
                           if p.stem not in ('go-reviewer', 'devops-reviewer')}
    drift = []
    for name in sorted(names):
        output = ROOT / '.claude/agents' / f'{name}.md'
        expected = claude_source(output)
        if not output.exists() or output.read_text() != expected:
            drift.append(str(output.relative_to(ROOT)))
            if not args.check:
                output.write_text(expected)
    # Canonical reusable skills retain native Claude discovery at the old paths.
    for canonical in sorted((ROOT / 'skills').rglob('*')):
        if not canonical.is_file():
            continue
        output = ROOT / '.claude/skills' / canonical.relative_to(ROOT / 'skills')
        expected = canonical.read_text(encoding='utf-8')
        if not output.exists() or output.read_text(encoding='utf-8') != expected:
            drift.append(str(output.relative_to(ROOT)))
            if not args.check:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(expected, encoding='utf-8')
    if args.check and drift:
        parser.exit(1, 'role bridge drift: ' + ', '.join(drift) + '\n')
    print('role bridges verified' if args.check else f'role bridges regenerated ({len(drift)} changed)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
