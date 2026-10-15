"""Read-only workspace inventory. Never imports or executes project code."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit, urlunsplit

SKIP = {'.git', '.sdlc', '.venv', 'venv', 'node_modules', '__pycache__', 'vendor', 'dist', 'build', '.cache'}
INSTRUCTIONS = ('AGENTS.md', 'AGENTS.override.md', 'CLAUDE.md', 'QWEN.md', '.cursorrules',
                'opencode.json', 'opencode.jsonc', '.mcp.json', '.claude/settings.json',
                '.cursor/mcp.json', '.cursor/cli.json', '.codex/config.toml')


def _text(path: Path, limit: int = 262144) -> str:
    if path.is_symlink() or not path.is_file():
        return ''
    with path.open('r', encoding='utf-8', errors='replace') as stream:
        return stream.read(limit)


def _git(path: Path, *args: str) -> str:
    try:
        result = subprocess.run(['git', '-c', 'core.hooksPath=/dev/null', '-C', str(path), *args],
                                capture_output=True, text=True, timeout=10,
                                env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0', 'GIT_TERMINAL_PROMPT': '0'})
        return result.stdout.strip() if result.returncode == 0 else ''
    except (OSError, subprocess.TimeoutExpired):
        return ''


def _remote(value: str) -> str:
    """Retain repository identity, never URL credentials, query strings or fragments."""
    if '://' in value:
        try:
            parsed = urlsplit(value)
            host = parsed.hostname or ''
            if parsed.port:
                host += ':' + str(parsed.port)
            return urlunsplit((parsed.scheme, host, parsed.path, '', ''))
        except ValueError:
            return '[invalid remote URL]'
    return re.sub(r'^[^@/]+@', '', value).split('?', 1)[0].split('#', 1)[0]


def _files(root: Path):
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in SKIP and not (Path(directory) / d).is_symlink()
                         and not (Path(directory) / d / '.git').exists())
        for name in sorted(files):
            path = Path(directory) / name
            if not path.is_symlink():
                yield path.relative_to(root).as_posix()


def inspect_project(root: str | Path) -> dict:
    root = Path(root).resolve(strict=True)
    names = list(_files(root))
    commands: dict[str, list[str]] = {'format': [], 'lint': [], 'test': [], 'build': [], 'generate': []}
    languages, package_managers, generators = set(), set(), []
    if (root / 'go.mod').is_file():
        languages.add('go')
        package_managers.add('go')
        commands['test'].append('go test ./...')
        commands['build'].append('go build ./...')
    if any((root / x).is_file() for x in ('pyproject.toml', 'requirements.txt', 'setup.py', 'Pipfile')):
        languages.add('python')
        package_managers.add('uv' if (root / 'uv.lock').is_file() else 'pip')
        if any(x.startswith('tests/') or re.search(r'(^|/)test_[^/]+\.py$', x) for x in names):
            commands['test'].append('python3 -m pytest' if 'pytest' in _text(root / 'pyproject.toml')
                                    else 'python3 -m unittest discover -s tests')
    package_text = _text(root / 'package.json')
    if package_text:
        try:
            package = json.loads(package_text)
        except ValueError:
            package = {}
        languages.add('typescript' if (root / 'tsconfig.json').is_file() or any(x.endswith('.ts') for x in names)
                      else 'javascript')
        manager = 'pnpm' if (root / 'pnpm-lock.yaml').is_file() else 'yarn' if (root / 'yarn.lock').is_file() else 'npm'
        package_managers.add(manager)
        for name in package.get('scripts', {}):
            for category in commands:
                if name in (category, 'fmt' if category == 'format' else category):
                    commands[category].append(f'{manager} run {name}')
    suffixes = {'.rs': 'rust', '.java': 'java', '.cs': 'csharp', '.rb': 'ruby', '.php': 'php'}
    for extension, language in suffixes.items():
        if any(x.endswith(extension) for x in names):
            languages.add(language)
    for filename, prefix, pattern in [('Makefile', 'make', r'^([\w:.-]+)\s*:(?!=)'),
                                      ('Taskfile.yml', 'task', r'^  ([\w:.-]+):\s*$'),
                                      ('Taskfile.yaml', 'task', r'^  ([\w:.-]+):\s*$')]:
        targets = re.findall(pattern, _text(root / filename), re.MULTILINE)
        for category in commands:
            for target in targets:
                if target in (category, 'fmt' if category == 'format' else category):
                    commands[category].append(f'{prefix} {target}')
    for filename, tool in [('sqlc.yaml', 'sqlc'), ('sqlc.yml', 'sqlc'), ('buf.gen.yaml', 'buf'),
                            ('.mockery.yaml', 'mockery'), ('gqlgen.yml', 'gqlgen'), ('prisma/schema.prisma', 'prisma')]:
        if (root / filename).is_file():
            generators.append({'tool': tool, 'source': filename, 'status': 'detected_not_executed'})
    instruction_files = sorted(x for x in names if x in INSTRUCTIONS or x.endswith('/AGENTS.md')
                               or x.startswith(('.claude/', '.cursor/', '.opencode/', '.codex/')))
    ci = sorted(x for x in names if x.startswith(('.github/workflows/', '.circleci/'))
                or x in ('.gitlab-ci.yml', 'Jenkinsfile', 'azure-pipelines.yml'))
    remote_names = _git(root, 'remote').splitlines()
    remotes = {name: _remote(_git(root, 'remote', 'get-url', name)) for name in remote_names}
    gitdir = _git(root, 'rev-parse', '--absolute-git-dir')
    common = _git(root, 'rev-parse', '--git-common-dir')
    base = _git(root, 'symbolic-ref', '--short', 'refs/remotes/origin/HEAD')
    hooks_path = _git(root, 'config', '--local', '--get', 'core.hooksPath')
    hooks = Path(hooks_path) if hooks_path else Path(gitdir) / 'hooks' if gitdir else root / '.git/hooks'
    if not hooks.is_absolute():
        hooks = root / hooks
    hook_names = sorted(p.name for p in hooks.iterdir() if p.is_file() and not p.name.endswith('.sample')) if hooks.is_dir() else []
    return {'id': root.name, 'path': str(root), 'kind': 'git_repository' if gitdir else 'directory',
            'git': {'branch': _git(root, 'symbolic-ref', '--short', 'HEAD') or None,
                    'revision': _git(root, 'rev-parse', '--verify', 'HEAD') or None,
                    'default_branch': base.removeprefix('origin/') or None, 'remotes': remotes,
                    'worktree': bool(gitdir and common and (root / common).resolve() != Path(gitdir).resolve()),
                    'submodule': bool(_git(root, 'rev-parse', '--show-superproject-working-tree')),
                    'hooks_path': hooks_path or None, 'hook_names': hook_names},
            'languages': sorted(languages), 'package_managers': sorted(package_managers),
            'commands': {k: sorted(set(v)) for k, v in commands.items()}, 'command_status': 'suggested_not_executed',
            'generators': generators, 'instructions': instruction_files, 'ci': ci,
            'tests': sorted(x for x in names if x.startswith(('tests/', 'test/')) or
                            re.search(r'(_test\.go|\.test\.[cm]?[jt]sx?|/test_[^/]+\.py)$', x)),
            'relationships': {'depends_on': [], 'status': 'requires_review'}}


def discover_workspace(target: str | Path) -> dict:
    """Find nested Git roots, including gitfile worktrees/submodules; skip symlinks."""
    raw = Path(target).absolute()
    if raw.is_symlink():
        raise ValueError('workspace root must not be a symlink')
    root = raw.resolve(strict=True)
    if not root.is_dir():
        raise ValueError('workspace root must be a directory')
    repos, skipped = [], []
    for directory, dirs, files in os.walk(root, followlinks=False):
        path = Path(directory)
        if '.git' in dirs or '.git' in files:
            if (path / '.git').is_symlink():
                skipped.append(str(path / '.git'))
            else:
                repos.append(path)
        skipped.extend(str(path / d) for d in dirs if (path / d).is_symlink())
        dirs[:] = sorted(d for d in dirs if d not in SKIP and not (path / d).is_symlink())
    projects = [inspect_project(p) for p in sorted(repos)] if repos else [inspect_project(root)]
    # A second inventory excludes files owned by our installation so reinstallation is stable.
    manifest_path = root / '.sdlc/generated-manifest.json'
    owned = set()
    if manifest_path.is_file() and not manifest_path.is_symlink():
        try:
            owned = {name for name, entry in json.loads(_text(manifest_path, 4194304)).get('files', {}).items()
                     if entry.get('original') is None}
        except (ValueError, AttributeError):
            pass
    for project in projects:
        prefix = Path(project['path']).relative_to(root)
        project['instructions'] = [name for name in project['instructions']
                                   if (prefix / name).as_posix() not in owned]
    used = set()
    for project in projects:
        relative = Path(project['path']).relative_to(root).as_posix()
        ident = re.sub(r'[^a-zA-Z0-9_-]+', '-', relative if relative != '.' else root.name).strip('-') or 'project'
        if ident in used:
            raise ValueError('discovered project identifiers collide; set explicit IDs in workspace config')
        project['id'] = ident
        used.add(ident)
    return {'schema_version': 2, 'root': str(root), 'projects': projects,
            'skipped_symlinks': sorted(skipped), 'read_only': True,
            'secrets': 'secret files and environment values are not read',
            'warnings': ['Detected commands are suggestions; no project commands were executed.']}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', nargs='?')
    parser.add_argument('--target')
    args = parser.parse_args(argv)
    try:
        print(json.dumps(discover_workspace(args.target or args.path or '.'), indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError) as error:
        parser.exit(1, f'error: {error}\n')
