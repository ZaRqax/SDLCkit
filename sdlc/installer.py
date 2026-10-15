"""Shared installation engine: preview, ownership, atomic transactions and safe uninstall."""
from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager
import copy
import difflib
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile

from sdlc.discovery import discover_workspace, inspect_project
from sdlc.harness import PRIMARY, json_text, probe_harness, render_harness, select_harnesses

MANIFEST = '.sdlc/generated-manifest.json'
JOURNAL = '.sdlc/install-journal.json'
BEGIN = '<!-- BEGIN SDLCKIT MANAGED -->'
END = '<!-- END SDLCKIT MANAGED -->'


class ConflictError(ValueError):
    """An installation would replace user-owned or concurrently edited content."""


def confined(root: Path, relative: str) -> Path:
    rel = Path(relative)
    if rel.is_absolute() or '..' in rel.parts or not rel.parts:
        raise ValueError(f'path escapes installation root: {relative}')
    current = root
    for component in rel.parts:
        current = current / component
        if current.is_symlink():
            raise ValueError(f'symlink is not an installation target: {relative}')
    if not current.resolve().is_relative_to(root):
        raise ValueError(f'path escapes installation root: {relative}')
    return current


def _root(target) -> Path:
    raw = Path(target).absolute()
    # Resolve the chosen allowlist root (macOS /tmp itself has a symlinked ancestor),
    # then reject symlinks in every generated path below that canonical root.
    if raw.is_symlink():
        raise ValueError('installation root must not be a symlink')
    root = raw.resolve(strict=True)
    if not root.is_dir():
        raise ValueError('installation target must be a directory')
    return root


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _encoded(data: bytes | None):
    return None if data is None else base64.b64encode(data).decode('ascii')


def _decoded(value):
    return None if value is None else base64.b64decode(value, validate=True)


def _read(root: Path, name: str) -> bytes | None:
    path = confined(root, name)
    if path.exists() and not path.is_file():
        raise ConflictError(f'target is not a regular file: {name}')
    return path.read_bytes() if path.exists() else None


def _load_manifest(root: Path) -> dict:
    raw = _read(root, MANIFEST)
    if raw is None:
        return {'schema_version': 2, 'files': {}}
    value = json.loads(raw)
    if value.get('schema_version') != 2 or not isinstance(value.get('files'), dict):
        raise ValueError('invalid installation manifest')
    for name, entry in value['files'].items():
        confined(root, name)
        if not isinstance(entry, dict) or not isinstance(entry.get('generated_hash'), str):
            raise ValueError(f'invalid manifest entry: {name}')
    return value


def _atomic_write(root: Path, relative: str, data: bytes | None, mode=None):
    path = confined(root, relative)
    if data is None:
        if path.exists():
            path.unlink()
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    # Revalidate after mkdir before replacement, including .sdlc and nested provider folders.
    path = confined(root, relative)
    handle, temporary = tempfile.mkstemp(prefix='.sdlc-write-', dir=path.parent)
    try:
        with os.fdopen(handle, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode if mode is not None else 0o644)
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _cleanup_dirs(root: Path, names: list[str]):
    for name in sorted(set(names), key=lambda p: len(Path(p).parts), reverse=True):
        path = confined(root, name)
        try:
            path.rmdir()
        except (OSError, FileNotFoundError):
            pass


def recover(root: str | Path, dry_run=False) -> dict:
    root = _root(root)
    raw = _read(root, JOURNAL)
    if raw is None:
        return {'status': 'clean'}
    journal = json.loads(raw)
    if journal.get('schema_version') != 1 or not isinstance(journal.get('operations'), list):
        raise ConflictError('invalid recovery journal; inspect it before proceeding')
    # Preflight every restoration before touching any file. Unknown edits are always preserved.
    for operation in journal['operations']:
        current = _read(root, operation['path'])
        if current not in (_decoded(operation['before']), _decoded(operation['after'])):
            raise ConflictError(f'recovery would overwrite a user edit: {operation["path"]}')
    if dry_run:
        return {'status': 'recovery_required', 'operations': len(journal['operations'])}
    for operation in reversed(journal['operations']):
        _atomic_write(root, operation['path'], _decoded(operation['before']), operation.get('mode'))
    confined(root, JOURNAL).unlink()
    _cleanup_dirs(root, journal.get('created_directories', []))
    return {'status': 'recovered', 'operations': len(journal['operations'])}


@contextmanager
def _lock(root):
    import fcntl
    state = confined(root, '.sdlc')
    state.mkdir(exist_ok=True)
    lock = confined(root, '.sdlc/install.lock')
    with lock.open('a+b') as stream:
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ConflictError('another installation owns this workspace') from error
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _transaction(root: Path, operations: list[dict]):
    if not operations:
        return
    directories = []
    for operation in operations:
        path = confined(root, operation['path'])
        operation['mode'] = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600 if operation['path'] == MANIFEST else None
        for parent in path.parents:
            if parent == root:
                break
            if not parent.exists():
                directories.append(parent.relative_to(root).as_posix())
    journal = {'schema_version': 1, 'operations': operations, 'created_directories': directories}
    _atomic_write(root, JOURNAL, json_text(journal).encode(), 0o600)
    try:
        for operation in operations:
            # Catch cooperative concurrent modifications that happened after planning.
            if _read(root, operation['path']) != _decoded(operation['before']):
                raise ConflictError(f'file changed during install: {operation["path"]}')
            _atomic_write(root, operation['path'], _decoded(operation['after']), operation.get('mode'))
    except BaseException:
        recover(root)
        raise
    confined(root, JOURNAL).unlink()


def _op(name, before, after):
    return {'path': name, 'before': _encoded(before), 'after': _encoded(after)}


def _merge_block(before: bytes, generated: bytes) -> tuple[bytes, str]:
    text, body = before.decode('utf-8'), generated.decode('utf-8')
    if BEGIN in text or END in text:
        raise ConflictError('unowned managed block exists; restore its ownership manifest first')
    block = BEGIN + '\n' + body.rstrip() + '\n' + END
    separator = '' if not text or text.endswith('\n\n') else '\n' if text.endswith('\n') else '\n\n'
    return (text + separator + block + '\n').encode(), separator + block + '\n'


def _safe_diff(name, before, after, owned):
    # Never dump arbitrary user configuration or credentials into preview output.
    if before is not None and not owned:
        return f'{name}: user-owned content preserved by scoped merge (original body omitted)\n'
    return ''.join(difflib.unified_diff((before or b'').decode('utf-8').splitlines(True),
                    (after or b'').decode('utf-8').splitlines(True), fromfile=name, tofile=name))


def _configuration(config, target):
    if config is not None:
        from sdlc.config import default_config, merge_config, validate_config
        base = default_config()
        base['workspace']['root'] = str(Path(target).resolve())
        effective = merge_config(base, config)
        if 'roles' in config and not config['roles']:
            effective['roles'] = {}
        return validate_config(effective)
    from sdlc.config import load_for_target
    return load_for_target(target)


def _project_configuration(config: dict, project_root: Path, project_id: str) -> dict:
    """Merge a target profile over an explicit effective workspace configuration.

    The supplied workspace root/allowlist and inherited safety restrictions remain binding.
    Reading project policy is required even when setup received an already loaded config dict.
    """
    from sdlc.config import merge_config, read_document, validate_config
    local = copy.deepcopy(config)
    workspace = local.get('workspace', {})
    workspace_root = Path(workspace.get('root', project_root)).resolve()
    allowlist = [workspace_root] + [(workspace_root / path).resolve() for path in workspace.get('allowed_paths', [])]
    if not any(project_root.is_relative_to(path) for path in allowlist):
        raise ValueError('project profile escapes the configured workspace allowlist')
    selected = next((copy.deepcopy(entry) for entry in workspace.get('projects', [])
                     if (workspace_root / entry['path']).resolve() == project_root), None)
    existing = local.get('project', {})
    if selected is None and (not existing.get('path') or Path(existing['path']).resolve() == project_root):
        selected = copy.deepcopy(existing)
    selected = selected or {'id': project_id, 'path': str(project_root)}
    for filename in ('project.yaml', 'project.json'):
        profile = confined(project_root, '.sdlc/' + filename)
        if profile.is_file():
            layer = read_document(profile)
            if layer.get('schema_version') != 2 or not isinstance(layer.get('project'), dict):
                raise ValueError(f'invalid project profile: {profile}')
            selected = merge_config(selected, layer['project'])
            break
    for key in ('policy', 'verification', 'agent', 'workflow', 'delivery', 'parallelism'):
        if key in selected:
            local[key] = merge_config(local.get(key, {}), selected[key], key)
    selected['path'] = str(project_root)
    selected.setdefault('id', project_id)
    local['project'] = selected
    return validate_config(local)


def _render_plan(root: Path, harness: str, profile: str, config) -> tuple[dict, dict]:
    inventory = discover_workspace(root)
    effective = _configuration(config, root)
    configuration_base = copy.deepcopy(effective)
    declared = effective.get('workspace', {}).get('projects', [])
    selected_projects = inventory['projects']
    if declared:
        selected_projects = []
        configured_root = Path(effective['workspace']['root'])
        for entry in declared:
            configured_path = (configured_root / entry['path']).resolve()
            if not configured_path.is_relative_to(root):
                # A shared registry may include explicitly allowlisted disjoint roots.
                # Each target manifest owns only projects below that target.
                continue
            candidate = next((p for p in inventory['projects'] if Path(p['path']) == configured_path), None)
            candidate = copy.deepcopy(candidate or inspect_project(configured_path))
            candidate['id'] = entry['id']
            selected_projects.append(candidate)
        if not selected_projects:
            raise ValueError('no declared projects are inside this target; select a registered project root')
    owned = _load_manifest(root)['files']
    for project in selected_projects:
        prefix = Path(project['path']).relative_to(root)
        project['instructions'] = [name for name in project['instructions']
                                   if not (owned.get((prefix / name).as_posix(), {}).get('original') is None
                                           and (prefix / name).as_posix() in owned)]
    for project in inventory['projects']:
        selected = next((p for p in selected_projects if p['path'] == project['path']), None)
        if selected:
            project['id'] = selected['id']
    # Workspace evidence excludes a transient per-repo selection loaded by configuration.
    effective.pop('project', None)
    if not declared:
        effective.setdefault('workspace', {})['root'] = str(root)
        effective['workspace']['projects'] = [{'id': p['id'], 'path': str(Path(p['path']).resolve())}
                                             for p in selected_projects]
    for entry in effective['workspace']['projects']:
        entry['path'] = str((Path(effective['workspace']['root']) / entry['path']).resolve())
    selected = select_harnesses(harness, effective)
    if profile not in ('auto', 'generic', 'go'):
        raise ValueError('profile must be auto, generic or go')
    generated = {}
    for project in selected_projects:
        project_root = Path(project['path'])
        prefix = project_root.relative_to(root)
        if config is None:
            from sdlc.config import load_for_target
            local = load_for_target(project_root)
        else:
            local = _project_configuration(configuration_base, project_root, project['id'])
        explicit_commands = copy.deepcopy(local.get('project', {}).get('commands', {}))
        selected_profile = 'go' if profile == 'go' or profile == 'auto' and project['languages'] == ['go'] else 'generic'
        if selected_profile == 'go':
            from sdlc.config import apply_profile
            local = apply_profile(local, 'go')
        render_project = copy.deepcopy(project)
        render_project['commands'] = {**local.get('project', {}).get('commands', {}),
                                      **{key: value for key, value in project['commands'].items() if value},
                                      **explicit_commands}
        for name in selected:
            for relative, contents in render_harness(local, name, render_project).items():
                key = (prefix / relative).as_posix()
                entry = generated.setdefault(key, {'content': contents, 'harnesses': []})
                if entry['content'] != contents:
                    raise ValueError(f'adapters disagree on shared output: {key}')
                entry['harnesses'].append(name)
        key = (prefix / '.sdlc/project.json').as_posix()
        project_profile = {'schema_version': 2, 'project': {'id': project['id'], 'repository_root': '.',
            'kind': project['kind'], 'stack': {'languages': project['languages']},
            'commands': render_project['commands'], 'generated_paths': local.get('project', {}).get('generated_paths', []),
            'branches': {'base': project['git']['default_branch'] or 'auto'},
            'policy': local.get('policy', {'external_write': 'approval_required'})}}
        generated[(prefix / '.sdlc/discovery.json').as_posix()] = {'content': json_text(project), 'harnesses': selected}
        generated[key] = {'content': json_text(project_profile), 'harnesses': selected}
        generated[(prefix / '.sdlc/.gitignore').as_posix()] = {'content': '# Private SDLC runtime and ownership state\n/generated-manifest.json\n/install-journal.json\n/install.lock\n/local.*\n/runs/\n/deliveries/\n/backups/\n/*.sqlite*\n', 'harnesses': selected}
    generated['.sdlc/.gitignore'] = {'content': '# Private SDLC runtime and ownership state\n/generated-manifest.json\n/install-journal.json\n/install.lock\n/local.*\n/runs/\n/deliveries/\n/backups/\n/*.sqlite*\n', 'harnesses': selected}
    generated['.sdlc/workspace-map.json'] = {'content': json_text(inventory), 'harnesses': selected}
    # Keep effective config separate from workspace source to avoid overwriting user config.
    generated['.sdlc/effective-config.json'] = {'content': json_text(effective), 'harnesses': selected}
    source_names = ('.sdlc/workspace.yaml', '.sdlc/workspace.json')
    user_source = next((name for name in source_names if confined(root, name).is_file() and name not in owned), None)
    if user_source is None:
        generated['.sdlc/workspace.json'] = {'content': json_text(effective), 'harnesses': selected}
    return generated, {'inventory': inventory, 'harnesses': selected, 'effective_config': effective}


def _install_locked(root, harness, profile, dry_run, merge, config):
    recovery = recover(root, dry_run=dry_run)
    if recovery['status'] == 'recovery_required':
        raise ConflictError('interrupted transaction requires recovery; run without --dry-run or --recover')
    generated, report = _render_plan(root, harness, profile, config)
    manifest = _load_manifest(root)
    updated = copy.deepcopy(manifest)
    operations, changes, conflicts = [], [], []
    for name, output in sorted(generated.items()):
        before = _read(root, name)
        desired = output['content'].encode()
        old = manifest['files'].get(name)
        if old:
            if before is None or _hash(before) != old['generated_hash']:
                conflicts.append({'path': name, 'reason': 'kit-owned file has user edits or was removed'})
                continue
            entry = copy.deepcopy(old)
            if old.get('merge_segment'):
                original = _decoded(old['original'])
                desired, segment = _merge_block(original, desired)
                entry['merge_segment'] = segment
        elif before is not None:
            if merge and Path(name).suffix in ('.md', '.mdc'):
                desired, segment = _merge_block(before, desired)
                entry = {'original': _encoded(before), 'merge_segment': segment}
            else:
                conflicts.append({'path': name, 'reason': 'user-owned file; use --merge for Markdown or resolve explicitly'})
                continue
        else:
            entry = {'original': None}
        entry['generated_hash'] = _hash(desired)
        entry['harnesses'] = sorted(set(entry.get('harnesses', []) + output['harnesses']))
        updated['files'][name] = entry
        if before != desired:
            operations.append(_op(name, before, desired))
            changes.append({'path': name, 'ownership': 'kit-generated' if old or before is None else 'scoped-merge',
                            'diff': _safe_diff(name, before, desired, bool(old))})
    # Remove outputs for roles/integrations disabled since a previous install.
    for name, old in manifest['files'].items():
        if name in generated or not set(old.get('harnesses', [])).intersection(report['harnesses']):
            continue
        remaining = sorted(set(old.get('harnesses', [])) - set(report['harnesses']))
        if remaining:
            updated['files'][name]['harnesses'] = remaining
            continue
        before = _read(root, name)
        if before is None or _hash(before) != old['generated_hash']:
            conflicts.append({'path': name, 'reason': 'stale kit file has user edits'})
            continue
        after = _decoded(old['original'])
        operations.append(_op(name, before, after))
        updated['files'].pop(name)
        changes.append({'path': name, 'ownership': 'kit-generated', 'diff': _safe_diff(name, before, after, True)})
    report.update(dry_run=dry_run, changes=changes, conflicts=conflicts,
                  status='conflict' if conflicts else 'preview' if dry_run else 'installed')
    if conflicts:
        return report
    old_manifest = _read(root, MANIFEST)
    new_manifest = json_text(updated).encode()
    if old_manifest != new_manifest:
        operations.append(_op(MANIFEST, old_manifest, new_manifest))
    if not dry_run:
        _transaction(root, operations)
    report['operation_count'] = len(operations)
    return report


def install(target, harness='auto', profile='auto', dry_run=False, merge=False, config=None) -> dict:
    root = _root(target)
    if dry_run:
        return _install_locked(root, harness, profile, True, merge, config)
    with _lock(root):
        return _install_locked(root, harness, profile, False, merge, config)


def _uninstall_locked(root, dry_run, harness):
    recovery = recover(root, dry_run=dry_run)
    if recovery['status'] == 'recovery_required':
        raise ConflictError('interrupted transaction requires recovery')
    manifest = _load_manifest(root)
    updated = copy.deepcopy(manifest)
    operations, changes, conflicts = [], [], []
    for name, entry in reversed(list(manifest['files'].items())):
        if harness and harness not in entry.get('harnesses', []):
            continue
        if harness and set(entry.get('harnesses', [])) - {harness}:
            updated['files'][name]['harnesses'].remove(harness)
            continue
        before = _read(root, name)
        after = _decoded(entry['original'])
        if before is not None and _hash(before) != entry['generated_hash']:
            segment = entry.get('merge_segment')
            if segment and before.decode('utf-8').count(segment) == 1:
                # Preserve edits outside our exactly matching managed segment.
                after = before.decode('utf-8').replace(segment, '', 1).encode()
            else:
                conflicts.append({'path': name, 'reason': 'user edits preserved; restore/reconcile before uninstall'})
                continue
        if before != after:
            operations.append(_op(name, before, after))
            changes.append(name)
        updated['files'].pop(name)
    if conflicts:
        return {'status': 'conflict', 'conflicts': conflicts, 'changes': [], 'dry_run': dry_run}
    old_manifest = _read(root, MANIFEST)
    new_manifest = json_text(updated).encode() if updated['files'] else None
    if old_manifest != new_manifest:
        operations.append(_op(MANIFEST, old_manifest, new_manifest))
    if not dry_run:
        _transaction(root, operations)
        directories = [str(p) for name in changes for p in Path(name).parents if str(p) != '.']
        _cleanup_dirs(root, directories)
    return {'status': 'preview' if dry_run else 'uninstalled', 'changes': changes,
            'conflicts': [], 'dry_run': dry_run}


def uninstall(target, dry_run=False, harness=None) -> dict:
    root = _root(target)
    if dry_run:
        return _uninstall_locked(root, True, harness)
    with _lock(root):
        return _uninstall_locked(root, False, harness)


def doctor(target, config=None) -> dict:
    root = _root(target)
    from sdlc.config import explain_config
    effective = _configuration(config, root)
    probes = [probe_harness(name) for name in PRIMARY]
    integrations = []
    for name, value in effective.get('integrations', {}).items():
        if isinstance(value, dict):
            integrations.append({'id': name, 'enabled': value.get('enabled', False),
                                 'authentication': 'not_probed' if value.get('enabled') else 'not_required'})
    source = None
    for directory in (root, *root.parents):
        source = next((directory / '.sdlc' / filename for filename in ('workspace.yaml', 'workspace.json')
                       if (directory / '.sdlc' / filename).is_file()), None)
        if source:
            break
    if source and config is None:
        explanation = explain_config(source, project=root)
    else:
        explanation = {'effective': effective, 'sources': [str(source)] if source else [],
                       'provenance': {}, 'notes': ['Effective target configuration shown; generated project inventory is scoped to target.']}
    return {'schema_version': 1, 'inventory': discover_workspace(root), 'harnesses': probes,
            'effective_config': effective, 'configuration': explanation, 'integrations': integrations,
            'recovery': recover(root, dry_run=True),
            'permission_concerns': ['Harness permissions differ; generated instructions are not a security boundary.',
                                    'Enabled integration authentication is checked only on explicit connector use.'],
            'read_only': True}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', default='.')
    parser.add_argument('--harness', choices=(*PRIMARY, 'all', 'auto'), default='auto')
    parser.add_argument('--profile', default='auto', choices=('auto', 'generic', 'go'))
    parser.add_argument('--config')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--non-interactive', action='store_true', help='deterministic mode; never prompts')
    parser.add_argument('--merge', action='store_true', help='explicitly authorize a scoped Markdown block merge')
    parser.add_argument('--doctor', action='store_true')
    parser.add_argument('--list-installed', action='store_true')
    parser.add_argument('--uninstall', nargs='?', const='all', choices=(*PRIMARY, 'all'))
    parser.add_argument('--recover', action='store_true')
    args = parser.parse_args(argv)
    try:
        config = None
        if args.config:
            from sdlc.config import load_config
            config = load_config(args.config)
        if args.doctor:
            result = doctor(args.target, config)
        elif args.list_installed:
            result = _load_manifest(_root(args.target))
        elif args.recover:
            if args.dry_run:
                result = recover(args.target, True)
            else:
                with _lock(_root(args.target)):
                    result = recover(args.target)
        elif args.uninstall:
            result = uninstall(args.target, args.dry_run, None if args.uninstall == 'all' else args.uninstall)
        else:
            result = install(args.target, args.harness, args.profile, args.dry_run, args.merge, config)
        print(json_text(result), end='')
        return 1 if result.get('status') == 'conflict' else 0
    except (OSError, ValueError) as error:
        print(f'error: {error}', file=sys.stderr)
        return 1
