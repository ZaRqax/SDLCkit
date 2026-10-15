"""Effect-based safety decisions shared by delivery, runtime and local hooks.

This guard is defense in depth, not a shell sandbox. Harness permissions and
repository hooks still apply. Approval never overrides a deny rule or invariant.
"""
from __future__ import annotations

import fnmatch
import json
import re
import shlex
import sys
from pathlib import Path

LOCAL_EFFECTS = {'read', 'observe', 'local_read', 'inspect', 'search', 'local_edit', 'edit', 'test', 'verify',
                 'local_write', 'patch', 'commit', 'local_commit', 'local_branch', 'report',
                 'worktree', 'local_process'}
EXTERNAL_EFFECTS = {'external_write', 'remote_write', 'push', 'publish', 'github_pr', 'gitlab_mr',
                    'bitbucket_pr', 'issue_write', 'comment', 'transition', 'webhook', 'network_write'}
APPROVAL_EFFECTS = {'package_install', 'migration', 'data_change', 'infrastructure_change', 'high_risk_change'}
FORBIDDEN_EFFECTS = {'destructive', 'destructive_action', 'destructive_actions', 'force_push',
                     'merge', 'auto_merge', 'deploy', 'production_deploy', 'secret_read', 'secret_exposure'}


def evaluate_effect(effect: str, config: dict | None = None, approved=False, scope=None) -> dict:
    """Return a conservative decision for an effect and optional project scope.

    `approved=True` represents caller-supplied explicit authorization. Scoped
    authorization can instead be {effects: [...], scopes: [...]} and must match.
    Unknown effects fail closed. This function performs no side effects.
    """
    config = config or {}
    policy = config.get('policy', {})
    scope = str(scope or '')
    denied = policy.get('deny', [])
    for rule in denied:
        if fnmatch.fnmatchcase(effect, rule) or (scope and fnmatch.fnmatchcase(f'{effect}:{scope}', rule)):
            return {'decision': 'forbidden', 'effect': effect, 'scope': scope, 'reason': f'denied by policy: {rule}'}
    if effect in FORBIDDEN_EFFECTS:
        return {'decision': 'forbidden', 'effect': effect, 'scope': scope, 'reason': 'universal safety invariant'}
    allowed_effects = policy.get('allowed_effects')
    if allowed_effects is not None and effect not in allowed_effects:
        return {'decision': 'forbidden', 'effect': effect, 'scope': scope, 'reason': 'effect outside project allowlist'}
    authorized = approved is True
    if isinstance(approved, dict):
        effects = approved.get('effects', [])
        scopes = approved.get('scopes', [])
        authorized = effect in effects and bool(scope) and scope in scopes
    if effect in EXTERNAL_EFFECTS:
        gate = config.get('workflow', {}).get('gates', {}).get('external_writes', 'approval_required')
        if policy.get('external_write') == 'forbidden' or gate == 'forbidden':
            decision, reason = 'forbidden', 'external writes forbidden by effective policy'
        elif authorized:
            decision, reason = 'allow', 'explicit authorization for external write'
        else:
            decision, reason = 'approval_required', 'external writes require explicit authorization'
    elif effect in APPROVAL_EFFECTS or effect in policy.get('approval_required', []):
        if config.get('workflow', {}).get('gates', {}).get('high_risk_changes') == 'forbidden':
            return {'decision': 'forbidden', 'effect': effect, 'scope': scope, 'reason': 'high-risk changes forbidden by workflow'}
        decision = 'allow' if authorized else 'approval_required'
        reason = 'explicit authorization' if authorized else 'operation requires explicit authorization'
    elif effect in LOCAL_EFFECTS:
        allowed = policy.get('allowed_effects')
        if allowed is not None and effect not in allowed:
            decision, reason = 'forbidden', 'effect outside project allowlist'
        else:
            decision, reason = 'allow', 'scoped reversible local operation'
    else:
        decision, reason = 'forbidden', 'unknown effect; declare and implement policy before use'
    return {'decision': decision, 'effect': effect, 'scope': scope, 'reason': reason}


def require_effect(effect: str, config: dict | None = None, approved=False, scope=None) -> dict:
    result = evaluate_effect(effect, config, approved, scope)
    if result['decision'] != 'allow':
        raise PermissionError(f'{effect}: {result["decision"]}: {result["reason"]}')
    return result


def secret_path(path: str) -> bool:
    """Recognize credential paths without opening them or denying safe examples."""
    normalized = str(path).replace('\\', '/').strip('\"\'')
    name = normalized.rsplit('/', 1)[-1]
    if name == '.env' or (name.startswith('.env.') and not name.endswith(('.example', '.sample', '.template'))):
        return True
    if name in {'id_rsa', 'id_dsa', 'id_ecdsa', 'id_ed25519', '.netrc', '.npmrc', '.pypirc',
                'application_default_credentials.json', 'credentials.json', 'service-account.json'}:
        return True
    return '/.aws/credentials' in normalized or '/.ssh/' in normalized and not name.endswith('.pub')


def classify_command(command: str) -> str:
    """Classify observable dangerous commands; not a replacement for a sandbox."""
    lowered = command.lower()
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = []
    if tokens and tokens[0] in ('cat', 'head', 'tail', 'sed', 'awk', 'jq', 'less', 'more', 'rg'):
        if any(secret_path(token) for token in tokens[1:]):
            return 'secret_read'
    if re.search(r'\b(drop\s+(database|schema)|terraform\s+destroy)\b', lowered):
        return 'destructive'
    if '--no-preserve-root' in command:
        return 'destructive'
    if (re.search(r'\brm\b', command) and re.search(r'\s-[A-Za-z]*[rR]', command)
            and re.search(r'\s-[A-Za-z]*[fF]', command)
            and re.search(r'(?:\s|[\'"])(?:/\*?|~|\$HOME|\$\{HOME\})(?:[\'"\s;&|]|$)', command)):
        return 'destructive'
    if re.search(r'\bgit\s+(?:-[cC]\s+\S+\s+)*push\b', command):
        if re.search(r'--force(?:\b|-with-lease)|(?:\s)-[A-Za-z]*f(?:\s|$)', command):
            return 'force_push'
        return 'push'
    if re.search(r'\b(?:gh\s+pr|glab\s+mr)\s+merge\b', command):
        return 'merge'
    if re.search(r'\b(?:gh\s+pr|glab\s+mr)\s+(?:create|edit|close|review|comment)\b', command):
        return 'external_write'
    if re.search(r'\b(?:gh|glab)\s+api\b', command) and re.search(r'(?:--method|-X)\s*(?:POST|PUT|PATCH|DELETE)|(?:--field|-f|-F)\b', command, re.I):
        return 'external_write'
    if re.search(r'\b(?:curl|wget)\b', command) and re.search(r'(?:-X|--request)\s*(?:POST|PUT|PATCH|DELETE)|--data|-d\s', command, re.I):
        return 'external_write'
    if re.search(r'\b(?:kubectl\s+(?:delete|apply)|terraform\s+apply|git\s+reset\s+--hard)\b', command):
        return 'infrastructure_change'
    if re.search(r'\b(?:pip\d*\s+install|npm\s+(?:install|i)\b|go\s+get|apt(?:-get)?\s+install|brew\s+install)', command):
        return 'package_install'
    if re.search(r'\b(?:db:migrate|db:refresh|migrate\s+(?:up|down))', command):
        return 'migration'
    return 'local_process'


def generated_path(path: str, config: dict | None = None) -> bool:
    config = config or {}
    patterns = config.get('project', {}).get('generated_paths', []) + config.get('policy', {}).get('generated_paths', [])
    target = config.get('project', {}).get('path')
    if target:
        try:
            path = str(Path(path).resolve().relative_to(Path(target).resolve()))
        except ValueError:
            pass
    normalized = path.replace('\\', '/').lstrip('./')
    return any(fnmatch.fnmatchcase(normalized, pattern)
               or fnmatch.fnmatchcase('/' + normalized, pattern)
               or Path(normalized).match(pattern) for pattern in patterns)


def hook(mode: str) -> int:
    from .config import load_for_target
    try:
        data = json.load(sys.stdin)
        tool_input = data.get('tool_input', {}) or {}
        config = load_for_target(data.get('cwd') or Path.cwd())
    except (ValueError, OSError) as exc:
        print(f'BLOCKED: cannot validate tool safety: {exc}', file=sys.stderr)
        return 2
    if mode == 'pre-edit':
        path = tool_input.get('file_path') or tool_input.get('path', '')
        if secret_path(path) or generated_path(path, config):
            print('BLOCKED: secret or configured generated path; edit generator inputs instead', file=sys.stderr)
            return 2
    elif mode == 'pre-bash':
        decision = evaluate_effect(classify_command(tool_input.get('command', '')), config)
        if decision['decision'] == 'forbidden':
            print(f'BLOCKED: {decision["reason"]}', file=sys.stderr)
            return 2
        if decision['decision'] == 'approval_required':
            print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse',
                  'permissionDecision': 'ask', 'permissionDecisionReason': decision['reason']}}))
    elif mode != 'post-edit':
        print(f'unknown hook mode: {mode}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(hook(sys.argv[1] if len(sys.argv) > 1 else ''))
