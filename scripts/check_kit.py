#!/usr/bin/env python3
"""Verify the kit's sources and neutral configuration without external accounts."""
import ast
import json
from pathlib import Path
import re
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    errors = []
    required = (
        'AGENTS.md', 'CLAUDE.md', 'README.md', 'KIT-DEV.md', 'INSTALL.md', 'FLOW.md',
        'setup.sh', 'requirements.txt', '.mcp.json', 'config/defaults.yaml', 'config/roles.yaml',
        'config/security-policy.yaml', 'schemas/workspace-v2.json', 'scripts/sdlc.py',
        'scripts/discover-workspace.py', 'scripts/render-harness.py', 'scripts/runtime.py',
        'sdlc/config.py', 'sdlc/policy.py', 'sdlc/installer.py', 'sdlc/harness.py',
        'sdlc/integrations.py', 'sdlc/delivery.py', 'sdlc/runtime.py', 'sdlc/watch.py',
        'docs/onboarding.md', 'docs/compatibility.md', 'docs/orchestration.md',
        'integrations/requirements/README.md', 'integrations/delivery/README.md',
        'agents-config/pi/port-agents.py', 'agents-config/qwen/port-to-qwen.py',
        'agents-config/opencode/port-to-opencode.py', '.claude/commands/deliver.md',
    )
    for relative in required:
        if not (ROOT / relative).is_file():
            errors.append('missing ' + relative)
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    if not (ROOT / 'CLAUDE.md').read_text().startswith('@AGENTS.md'):
        errors.append('CLAUDE.md must import AGENTS.md')
    bridges = subprocess.run([sys.executable, str(ROOT / 'scripts/render-role-bridges.py'), '--check'],
                             cwd=ROOT, capture_output=True, text=True)
    if bridges.returncode:
        errors.append('canonical role bridge drift: ' + bridges.stderr.strip())
    roots = ('sdlc', 'scripts', 'tests', 'schemas', 'config', 'harnesses', 'roles', 'profiles',
             '.claude', 'templates', 'integrations', 'agents-config', '.claude-plugin')
    total = 0
    for folder in roots:
        for path in (ROOT / folder).rglob('*'):
            if not path.is_file() or '__pycache__' in path.parts:
                continue
            try:
                body = path.read_text(encoding='utf-8')
            except UnicodeDecodeError:
                continue
            relative = str(path.relative_to(ROOT))
            total += 1
            try:
                if path.suffix == '.py':
                    ast.parse(body, filename=relative)
                elif path.suffix == '.json':
                    json.loads(body)
                elif path.suffix in {'.yaml', '.yml'}:
                    from sdlc.config import read_document
                    read_document(path)
                elif path.suffix == '.sh':
                    subprocess.run(['bash', '-n', str(path)], check=True, capture_output=True)
                elif path.suffix == '.md' and folder == 'roles':
                    if not body.startswith('---\n'):
                        raise ValueError('canonical role requires metadata frontmatter')
            except Exception as exc:
                errors.append(f'{relative}: {exc}')
    for script in ('setup.sh', '.githooks/pre-commit'):
        result = subprocess.run(['bash', '-n', str(ROOT / script)], capture_output=True)
        if result.returncode:
            errors.append(f'{script}: shell syntax error')
    try:
        from sdlc.config import load_config, read_document
        load_config()
        from sdlc.workflows import validate_recipe
        for path in (ROOT / 'config/workflows').glob('*.yaml'):
            validate_recipe(read_document(path))
    except Exception as exc:
        errors.append('configuration/workflow validation: ' + str(exc))
    # Generic default rules must not require a particular provider, language or branch model.
    rules = (ROOT / 'AGENTS.md').read_text()
    for pattern in (r'You are a senior Go engineer', r'Primary agent = pi', r'Never skip phases',
                    r'GitFlow off `develop`', r'\*\*Serena.*your default'):
        if re.search(pattern, rules):
            errors.append('default instructions retain a mandatory legacy assumption: ' + pattern)
    # A read-only RLM utility remains separate from the write scheduler.
    workflow = ROOT / '.claude/workflows/rlm.js'
    if not workflow.exists():
        errors.append('legacy read-only RLM workflow missing')
    else:
        import shutil
        if shutil.which('node'):
            result = subprocess.run(['node', '-e',
                'const fs=require("fs");const s=fs.readFileSync(process.argv[1],"utf8").replace(/^export\\s+const\\s+meta/m,"const meta");new Function("args","budget","agent","parallel","pipeline","phase","log","return (async()=>{"+s+"\\n})()")',
                str(workflow)], capture_output=True)
            if result.returncode:
                errors.append('legacy RLM workflow syntax failed')
    if errors:
        print('\n'.join('FAIL: ' + error for error in errors), file=sys.stderr)
        return 1
    print(f'Kit structure, syntax, schemas, safety defaults and workflow contracts pass ({total} source files).')
    print('No remote systems, paid model calls or optional MCP servers were contacted.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
