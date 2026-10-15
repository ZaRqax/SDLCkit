#!/usr/bin/env python3
"""Stable neutral-role bridge consumed by retained legacy porters."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ALIASES = {'planner': 'analyst', 'tech-designer': 'architect', 'engineer': 'implementer',
           'qa-lead': 'verifier', 'go-code-reviewer': 'go-reviewer',
           'devops-lead': 'devops-reviewer', 'rlm': 'rlm'}
READONLY = {'explorer', 'reviewer', 'go-reviewer', 'devops-reviewer', 'rlm'}


def claude_source(path):
    """Return canonical neutral content with stable legacy Claude frontmatter."""
    path = Path(path)
    role = ALIASES.get(path.stem, path.stem)
    canonical = ROOT / 'roles' / f'{role}.md'
    if not canonical.is_file():
        return path.read_text(encoding='utf-8')
    import yaml
    _, frontmatter, body = canonical.read_text().split('---', 2)
    data = yaml.safe_load(frontmatter)
    tools = 'Read, Grep, Glob, Bash' if role in READONLY else 'Read, Write, Edit, Bash, Grep, Glob'
    return (f'---\nname: {path.stem}\ndescription: {data["purpose"]}\ntools: {tools}\nmodel: inherit\n---\n\n'
            f'<!-- Generated bridge from roles/{role}.md; regenerate with scripts/render-role-bridges.py. -->\n\n'
            + body.strip() + '\n')
