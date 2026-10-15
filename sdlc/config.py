"""Versioned configuration, provenance and non-weakening policy merge.

YAML requires PyYAML; JSON loading works with the standard library. JSON Schema
validation uses jsonschema when installed and always runs the semantic checks.
No configuration text is evaluated as Python or shell code.
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = ROOT / 'config/defaults.yaml'
SCHEMA = ROOT / 'schemas/workspace-v2.json'


def read_document(path: str | Path) -> dict:
    path = Path(path)
    try:
        text = path.read_text(encoding='utf-8')
    except OSError as exc:
        raise ValueError(f'cannot read configuration {path}: {exc}') from exc
    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f'duplicate configuration key {key!r} in {path}')
            result[key] = value
        return result
    try:
        data = json.loads(text, object_pairs_hook=unique_pairs)
    except json.JSONDecodeError:
        try:
            import yaml
        except ImportError as exc:
            raise ValueError('YAML configuration requires PyYAML; install requirements.txt or use JSON') from exc

        class UniqueLoader(yaml.SafeLoader):
            pass

        def mapping(loader, node, deep=False):
            result = {}
            for key_node, value_node in node.value:
                key = loader.construct_object(key_node, deep=deep)
                if key in result:
                    raise ValueError(f'duplicate configuration key {key!r} in {path}')
                result[key] = loader.construct_object(value_node, deep=deep)
            return result

        UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
        try:
            data = yaml.load(text, Loader=UniqueLoader)
        except yaml.YAMLError as exc:
            raise ValueError(f'invalid YAML in {path}: {exc}') from exc
    if not isinstance(data, dict):
        raise ValueError(f'configuration {path} must be an object')
    return data


def merge_config(base: dict, override: dict, key: str = '') -> dict:
    """Maps merge recursively, named role lists merge, deny rules union.

    Other lists (including commands) replace their predecessor. Safety settings
    can tighten to forbidden, but cannot be weakened by a lower-precedence layer.
    """
    result = copy.deepcopy(base)
    for name, value in override.items():
        dotted = f'{key}.{name}'.strip('.')
        old = result.get(name)
        if name == 'deny' and isinstance(old, list) and isinstance(value, list):
            result[name] = list(dict.fromkeys(old + value))
        elif dotted == 'policy.allowed_effects' and isinstance(old, list) and isinstance(value, list):
            result[name] = [item for item in old if item in value]
        elif dotted == 'policy.approval_required' and isinstance(old, list) and isinstance(value, list):
            result[name] = list(dict.fromkeys(old + value))
        elif dotted in ('policy.external_write', 'workflow.gates.external_writes', 'policy.destructive_actions',
                        'workflow.gates.destructive_actions', 'workflow.gates.high_risk_changes'):
            rank = {'allow': 0, 'approval_required': 1, 'forbidden': 2}
            if old in rank and value in rank and rank[value] < rank[old]:
                raise ValueError(f'{dotted} cannot weaken inherited safety policy {old!r}')
            result[name] = copy.deepcopy(value)
        elif name == 'roles' and isinstance(old, dict) and isinstance(value, list):
            if len({item['id'] for item in value}) != len(value):
                raise ValueError('roles ids must be unique')
            named = {item['id']: {k: v for k, v in item.items() if k != 'id'} for item in value}
            result[name] = merge_config(old, named, dotted)
        elif isinstance(old, dict) and isinstance(value, dict):
            result[name] = merge_config(old, value, dotted)
        elif name == 'roles' and isinstance(old, list) and isinstance(value, list):
            named = {item['id']: copy.deepcopy(item) for item in old}
            for item in value:
                named[item['id']] = merge_config(named.get(item['id'], {}), item)
            result[name] = list(named.values())
        else:
            result[name] = copy.deepcopy(value)
    return result


def default_config() -> dict:
    """Read canonical defaults, non-weakening safety and neutral role selection."""
    result = read_document(DEFAULTS)
    security_path = ROOT / 'config/security-policy.yaml'
    roles_path = ROOT / 'config/roles.yaml'
    if security_path.exists():
        result = merge_config(result, {'policy': read_document(security_path).get('policy', {})})
    if roles_path.exists():
        result['roles'] = read_document(roles_path).get('roles', {})
    return result


def _under(path: Path, parents: list[Path]) -> bool:
    return any(path == parent or parent in path.parents for parent in parents)


def validate_config(config: dict) -> dict:
    """Validate an effective schema-v2 dict and return an independent copy."""
    if not isinstance(config, dict):
        raise ValueError('configuration must be an object')
    try:
        import jsonschema
    except ImportError as exc:
        raise ValueError('configuration validation requires jsonschema; install requirements.txt') from exc
    try:
        jsonschema.Draft202012Validator(json.loads(SCHEMA.read_text())).validate(config)
    except jsonschema.ValidationError as exc:
        location = '.'.join(str(p) for p in exc.absolute_path) or '<root>'
        raise ValueError(f'{location}: {exc.message}') from exc
    if config['delivery']['default'] not in config['delivery']['allowed']:
        raise ValueError('delivery.default must be included in delivery.allowed')
    if config['requirements']['fallback'] not in config['requirements']['enabled']:
        raise ValueError('requirements.fallback must be enabled')
    if config['policy'].get('external_write') not in ('approval_required', 'forbidden'):
        raise ValueError('external writes require approval or must be forbidden')
    ids = [p['id'] for p in config['workspace']['projects']]
    if len(set(ids)) != len(ids):
        raise ValueError('workspace.projects ids must be unique')
    workspace = config['workspace']
    root = Path(workspace['root']).expanduser().resolve()
    allowed = [root] + [(root / p).expanduser().resolve() for p in workspace.get('allowed_paths', [])]
    paths = []
    for project in workspace['projects']:
        if 'path' not in project:
            raise ValueError(f'workspace project {project["id"]!r} requires path')
        path = (root / project['path']).resolve()
        if not _under(path, allowed):
            raise ValueError(f'project {project["id"]!r} path escapes workspace allowlist: {path}')
        paths.append(path)
        for dep in project.get('relationship', {}).get('depends_on', []):
            if dep not in ids or dep == project['id']:
                raise ValueError(f'project {project["id"]!r} has invalid dependency {dep!r}')
    if len(set(paths)) != len(paths):
        raise ValueError('workspace.projects paths must be unique')
    # Reject dependency cycles before any worktree or worker can be launched.
    graph = {p['id']: p.get('relationship', {}).get('depends_on', []) for p in workspace['projects']}
    active, done = set(), set()
    def visit(node):
        if node in active:
            raise ValueError(f'project dependency cycle at {node!r}')
        if node in done:
            return
        active.add(node)
        for dependency in graph[node]:
            visit(dependency)
        active.remove(node)
        done.add(node)
    for node in graph:
        visit(node)
    names = set()
    for server in config['integrations'].get('custom_mcp', []):
        name = server.get('id') or server.get('name')
        if not name or name in names:
            raise ValueError('custom MCP servers require unique id or name')
        names.add(name)
        if server.get('enabled') and not (server.get('command') or server.get('url')):
            raise ValueError(f'custom MCP {name!r} requires command or url')
        # References may use environment interpolation; literal credentials are rejected.
        for env_key, value in server.get('env', {}).items():
            if any(word in env_key.upper() for word in ('TOKEN', 'SECRET', 'PASSWORD', 'API_KEY')):
                if value and not value.startswith('${'):
                    raise ValueError(f'custom MCP {name!r}: {env_key} must reference an environment variable')
    role_overrides = config.get('roles', {})
    role_ids = [item['id'] for item in role_overrides] if isinstance(role_overrides, list) else list(role_overrides)
    available = {file.stem for file in (ROOT / 'roles').glob('*.md')}
    if len(set(role_ids)) != len(role_ids):
        raise ValueError('roles ids must be unique')
    for role_id in role_ids:
        if role_id not in available:
            raise ValueError(f'unknown canonical role: {role_id}')
    return copy.deepcopy(config)


def _workspace_path(path: str | Path | None) -> Path | None:
    if path is not None:
        candidate = Path(path).expanduser().resolve()
        if candidate.is_dir():
            candidate = next((candidate / '.sdlc' / name for name in ('workspace.yaml', 'workspace.json')
                              if (candidate / '.sdlc' / name).is_file()), candidate / '.sdlc/workspace.yaml')
        if not candidate.is_file():
            raise ValueError(f'workspace configuration not found: {candidate}')
        return candidate
    env_path = os.environ.get('SDLC_CONFIG')
    if env_path:
        return _workspace_path(env_path)
    for directory in [Path.cwd(), *Path.cwd().parents]:
        for name in ('workspace.yaml', 'workspace.json'):
            candidate = directory / '.sdlc' / name
            if candidate.is_file():
                return candidate
    return None


def explain_config(path: str | Path | None = None, project: str | Path | dict | None = None) -> dict:
    """Effective values and the winning source for each leaf setting.

    Relative workspace.root is resolved from the directory containing .sdlc,
    or the config file's parent for a config outside a .sdlc directory.
    Explicit allowed_paths is the user's path allowlist; symlinks are resolved.
    """
    effective = default_config()
    sources, provenance = [str(DEFAULTS)], {}
    def record(data, source, prefix=''):
        for key, value in data.items():
            dotted = f'{prefix}.{key}'.strip('.')
            if isinstance(value, dict):
                record(value, source, dotted)
            else:
                provenance[dotted] = source
    record(effective, str(DEFAULTS))
    for canonical_name, top_key in (('roles.yaml', 'roles'), ('security-policy.yaml', 'policy')):
        canonical = ROOT / 'config' / canonical_name
        if canonical.exists():
            document = read_document(canonical)
            record({top_key: document.get(top_key, {})}, str(canonical))
            sources.append(str(canonical))
    config_path = _workspace_path(path)
    layers = []
    if config_path:
        base = config_path.parent.parent if config_path.parent.name == '.sdlc' else config_path.parent
        workspace_layer = read_document(config_path)
        if workspace_layer.get('schema_version', 2) != 2:
            raise ValueError('unsupported schema_version; migrate the legacy roster before loading a workspace')
        workspace_layer.setdefault('workspace', {})
        workspace_layer['workspace']['root'] = str((base / workspace_layer['workspace'].get('root', '.')).resolve())
        layers.append((config_path, workspace_layer))
        for name in ('local.yaml', 'local.json'):
            local = config_path.parent / name
            if local.exists() and local != config_path:
                local_layer = read_document(local)
                if isinstance(local_layer.get('workspace'), dict) and 'root' in local_layer['workspace']:
                    local_layer['workspace']['root'] = str((base / local_layer['workspace']['root']).resolve())
                layers.append((local, local_layer))
    else:
        effective['workspace']['root'] = str(Path.cwd().resolve())
    inherited_workspace = None
    for source, layer in layers:
        if inherited_workspace is not None and isinstance(layer.get('workspace'), dict):
            workspace_override = layer['workspace']
            inherited_root = Path(inherited_workspace['root']).resolve()
            inherited_allowlist = [inherited_root] + [(inherited_root / value).resolve()
                                    for value in inherited_workspace.get('allowed_paths', [])]
            if 'root' in workspace_override and Path(workspace_override['root']).resolve() != inherited_root:
                raise ValueError('local overrides cannot change the declared workspace root')
            for value in workspace_override.get('allowed_paths', []):
                if not _under((inherited_root / value).resolve(), inherited_allowlist):
                    raise ValueError('local overrides cannot expand the workspace allowlist')
        effective = merge_config(effective, layer)
        if inherited_workspace is None:
            inherited_workspace = copy.deepcopy(effective['workspace'])
        record(layer, str(source))
        sources.append(str(source))
    effective = validate_config(effective)
    workspace_root = Path(effective['workspace']['root'])
    effective['workspace']['root'] = str(workspace_root.resolve())
    for entry in effective['workspace']['projects']:
        entry['path'] = str((workspace_root / entry['path']).resolve())
    if project is not None:
        selected = None
        if isinstance(project, dict):
            selected = project
        else:
            selected = next((item for item in effective['workspace']['projects'] if item['id'] == str(project)
                             or Path(item['path']) == Path(project).expanduser().resolve()), None)
            if selected is None:
                candidate = Path(project).expanduser().resolve()
                if candidate.is_dir():
                    selected = {'id': candidate.name, 'path': str(candidate)}
                else:
                    raise ValueError(f'unknown project: {project}')
        selected = copy.deepcopy(selected)
        project_path = (workspace_root / selected.get('path', selected.get('repository_root', '.'))).resolve()
        allowlist = [workspace_root.resolve()] + [(workspace_root / p).resolve() for p in effective['workspace'].get('allowed_paths', [])]
        if not _under(project_path, allowlist):
            raise ValueError(f'project path escapes workspace allowlist: {project_path}')
        project_file = next((project_path / '.sdlc' / name for name in ('project.yaml', 'project.json')
                             if (project_path / '.sdlc' / name).is_file()), project_path / '.sdlc/project.yaml')
        if project_file.exists():
            layer = read_document(project_file)
            if layer.get('schema_version', 2) != 2 or not isinstance(layer.get('project'), dict):
                raise ValueError(f'invalid project profile: {project_file}')
            selected = merge_config(selected, layer['project'])
            sources.append(str(project_file))
            record(layer, str(project_file))
        # Project policy and command overrides apply only to the selected project.
        for key in ('policy', 'verification', 'agent', 'workflow', 'delivery', 'parallelism'):
            if key in selected:
                effective[key] = merge_config(effective.get(key, {}), selected[key], key)
                record({key: selected[key]}, str(project_file) if project_file.exists() else 'workspace.projects')
        selected['path'] = str(project_path)
        effective['project'] = selected
    return {'effective': validate_config(effective), 'sources': sources, 'provenance': provenance,
            'notes': ['Explicit repository AGENTS.md remains authoritative; it is preserved, never parsed as executable policy.',
                      'Maps merge; named role lists merge by id; deny lists union; other lists replace.',
                      'Safety settings cannot weaken inherited restrictions.']}


def load_config(path: str | Path | None = None, project: str | Path | dict | None = None) -> dict:
    """Return the effective schema-v2 configuration as a plain dict."""
    return explain_config(path, project)['effective']


WORKFLOW_CONDITIONS = {'always', 'nontrivial', 'requires_review', 'high_risk'}


def validate_workflow(workflow: dict, roles: dict | None = None) -> dict:
    """Validate a workflow DAG using a bounded condition vocabulary, never eval."""
    if not isinstance(workflow, dict) or workflow.get('schema_version') != 1:
        raise ValueError('workflow schema_version must be 1')
    if not isinstance(workflow.get('id'), str) or not workflow['id']:
        raise ValueError('workflow id is required')
    stages = workflow.get('stages')
    if not isinstance(stages, list) or not stages:
        raise ValueError('workflow requires nonempty stages')
    role_map = roles if roles is not None else read_document(ROOT / 'config/roles.yaml')['roles']
    ids, graph = set(), {}
    for stage in stages:
        if not isinstance(stage, dict) or not isinstance(stage.get('id'), str):
            raise ValueError('workflow stages require ids')
        if stage['id'] in ids:
            raise ValueError(f'duplicate workflow stage {stage["id"]}')
        ids.add(stage['id'])
        if stage.get('role') not in role_map:
            raise ValueError(f'unknown role {stage.get("role")!r}')
        if stage.get('when', 'always') not in WORKFLOW_CONDITIONS:
            raise ValueError('unsupported workflow condition; arbitrary expressions are forbidden')
        if not isinstance(stage.get('needs', []), list) or not all(isinstance(n, str) for n in stage.get('needs', [])):
            raise ValueError('stage needs must be a list of stage ids')
        graph[stage['id']] = stage.get('needs', [])
    active, done = set(), set()
    def visit(stage):
        if stage in active:
            raise ValueError(f'workflow dependency cycle at {stage}')
        if stage in done:
            return
        active.add(stage)
        for dependency in graph[stage]:
            if dependency not in ids:
                raise ValueError(f'unknown workflow dependency {dependency}')
            visit(dependency)
        active.remove(stage)
        done.add(stage)
    for stage in ids:
        visit(stage)
    gates = workflow.get('gates', {})
    if gates.get('destructive', 'forbidden') != 'forbidden':
        raise ValueError('workflow cannot allow destructive actions')
    if gates.get('external_write', 'approval_required') not in ('approval_required', 'forbidden'):
        raise ValueError('workflow cannot waive external-write approval')
    return copy.deepcopy(workflow)


def load_workflow(name: str, context: dict | None = None) -> dict:
    if name not in ('quick-fix', 'feature', 'cross-repo', 'investigation', 'high-risk'):
        raise ValueError(f'unknown workflow {name!r}')
    workflow = validate_workflow(read_document(ROOT / 'config/workflows' / f'{name}.yaml'))
    context = context or {}
    conditions = {'always': True, 'nontrivial': context.get('complexity') != 'trivial',
                  'requires_review': bool(context.get('requires_review', True)),
                  'high_risk': bool(context.get('high_risk', False))}
    for stage in workflow['stages']:
        stage['selected'] = conditions[stage.get('when', 'always')]
    return workflow


def load_for_target(target: str | Path, path: str | Path | None = None) -> dict:
    """Load policy for an explicitly requested local target, including its profile.

    An explicit --repo/--root selects a local path; it grants no remote effects.
    An existing workspace allowlist remains binding. Without a workspace file,
    the target is the root and its own project profile supplies stricter policy.
    """
    target = Path(target).expanduser().resolve()
    if not target.is_dir():
        raise ValueError(f'target directory not found: {target}')
    config_path = _workspace_path(path) if path is not None else None
    if config_path is None:
        for directory in [target, *target.parents]:
            for name in ('workspace.yaml', 'workspace.json'):
                candidate = directory / '.sdlc' / name
                if candidate.is_file():
                    config_path = candidate
                    break
            if config_path:
                break
    if config_path:
        return load_config(config_path, project=target)
    effective = default_config()
    effective['workspace']['root'] = str(target)
    selected = {'id': target.name or 'project', 'path': str(target)}
    for name in ('project.yaml', 'project.json'):
        profile = target / '.sdlc' / name
        if profile.is_file():
            document = read_document(profile)
            if document.get('schema_version') != 2 or not isinstance(document.get('project'), dict):
                raise ValueError(f'invalid project profile: {profile}')
            selected = merge_config(selected, document['project'])
            break
    for key in ('policy', 'verification', 'agent', 'workflow', 'delivery', 'parallelism'):
        if key in selected:
            effective[key] = merge_config(effective[key], selected[key], key)
    selected['path'] = str(target)
    effective['project'] = selected
    return validate_config(effective)


def apply_profile(config: dict, name: str = 'generic') -> dict:
    """Apply a reviewed optional profile without overriding project commands."""
    result = copy.deepcopy(config)
    if name in ('auto', 'generic', 'none'):
        return result
    if name != 'go':
        raise ValueError(f'unknown profile: {name}')
    profile = read_document(ROOT / 'profiles/go/profile.yaml')
    selected = result.setdefault('project', {'id': Path(result['workspace']['root']).name or 'project',
                                             'path': result['workspace']['root']})
    selected['commands'] = merge_config(profile.get('commands', {}), selected.get('commands', {}))
    selected['generated_paths'] = list(dict.fromkeys(profile.get('generated_paths', []) + selected.get('generated_paths', [])))
    result['profiles'] = list(dict.fromkeys(result.get('profiles', []) + [name]))
    for role in profile.get('roles', []):
        result.setdefault('roles', {}).setdefault(role, {})['enabled'] = True
    return validate_config(result)


def main(argv=None):
    """CLI: config [effective|explain|validate] [PATH] [--project ID_OR_PATH]."""
    import argparse
    parser = argparse.ArgumentParser(description='Inspect effective SDLCkit configuration and provenance')
    parser.add_argument('action', nargs='?', choices=('effective', 'explain', 'validate'), default='effective')
    parser.add_argument('path', nargs='?')
    parser.add_argument('--config', dest='config_path')
    parser.add_argument('--project')
    args = parser.parse_args(argv)
    try:
        report = explain_config(args.config_path or args.path, args.project)
        for workflow_path in sorted((ROOT / 'config/workflows').glob('*.yaml')):
            validate_workflow(read_document(workflow_path))
    except (ValueError, OSError) as exc:
        parser.exit(1, f'configuration error: {exc}\n')
    if args.action == 'validate':
        print('configuration and workflow references valid')
    else:
        print(json.dumps(report if args.action == 'explain' else report['effective'], indent=2, sort_keys=True))
    return 0
