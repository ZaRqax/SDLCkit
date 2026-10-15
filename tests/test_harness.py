"""Native format snapshots and real executable-version probe semantics."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from sdlc import harness

FIXTURE_CONFIG = {'schema_version': 2, 'roles': {'engineer': {'enabled': True}, 'reviewer': {'enabled': True},
                   'go-reviewer': {'enabled': False}}, 'workflow': {'default': 'feature'}, 'integrations': {}}
FIXTURE_PROJECT = {'commands': {'test': ['python3 -m unittest discover -s tests']}}


class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        (root / 'roles').mkdir()
        for name in ('engineer', 'reviewer'):
            (root / 'roles' / (name + '.md')).write_text('---\nid: ' + name + '\ncapabilities: ' + ('[read, edit, shell]' if name == 'engineer' else '[read]') + '\nallowed_effects: ' + ('[read, local_edit, test]' if name == 'engineer' else '[read]') + '\n---\n\n'
                + ('Implement the scoped task and run project checks.' if name == 'engineer' else
                   'Review the changed code; report evidence and severity. Do not edit files.') + '\n')
        self.patch = patch.object(harness, 'KIT_ROOT', root)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_native_snapshots(self):
        fixture_root = Path(__file__).resolve().parents[1] / 'harnesses'
        for name in harness.PRIMARY:
            with self.subTest(harness=name):
                generated = harness.render_harness(FIXTURE_CONFIG, name, FIXTURE_PROJECT)
                expected = json.loads((fixture_root / name / 'snapshot.json').read_text())
                self.assertEqual(generated, expected)
                self.assertEqual(generated, harness.render_harness(FIXTURE_CONFIG, name, FIXTURE_PROJECT))
                self.assertNotIn('go-reviewer', '\n'.join(generated))

    def test_codex_toml_parses_and_inherits(self):
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib
        outputs = harness.render_harness(FIXTURE_CONFIG, 'codex')
        for name, text in outputs.items():
            if name.endswith('.toml'):
                parsed = tomllib.loads(text)
                self.assertNotIn('model', parsed)
        self.assertEqual(tomllib.loads(outputs['.codex/config.toml'])['approval_policy'], 'on-request')

    def test_enabled_only_mcp_and_provider_env_translation(self):
        config = {**FIXTURE_CONFIG, 'integrations': {'jira': {'enabled': False}, 'custom_mcp': [
            {'id': 'disabled', 'enabled': False, 'command': 'forbidden'},
            {'id': 'docs', 'enabled': True, 'command': 'docs-server', 'env': {'API_TOKEN': '${API_TOKEN}'}}]}}
        for name in harness.PRIMARY:
            outputs = harness.render_harness(config, name)
            self.assertNotIn('forbidden', json.dumps(outputs))
            self.assertNotIn('jira', json.dumps(outputs))
            if name == 'opencode':
                native = json.loads(outputs['opencode.json'])
                self.assertEqual(native['mcp']['servers']['docs']['environment']['API_TOKEN'], '{env:API_TOKEN}')
            if name == 'codex':
                self.assertIn('env_vars = ["API_TOKEN"]', outputs['.codex/config.toml'])

    def test_literal_secret_env_refused(self):
        config = {**FIXTURE_CONFIG, 'integrations': {'custom_mcp': [
            {'id': 'docs', 'enabled': True, 'command': 'server', 'env': {'TOKEN': 'a-secret-value'}}]}}
        with self.assertRaisesRegex(ValueError, 'secret values'):
            harness.render_harness(config, 'claude')

    def test_probe_real_version_process_and_honest_missing(self):
        with patch.object(harness.shutil, 'which', return_value='/fixture/codex'), patch.object(
                harness.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, 'codex-cli 0.162.1\n', '')) as run:
            result = harness.probe_harness('codex')
        self.assertEqual(run.call_args.args[0], ['/fixture/codex', '--version'])
        self.assertEqual(result['version'], ['codex-cli 0.162.1'])
        self.assertIn('authenticated execution was not performed', result['limitations'][0])
        with patch.object(harness.shutil, 'which', return_value=None):
            result = harness.probe_harness('cursor')
        self.assertEqual(result['status'], 'unavailable')

    def test_unknown_harness_and_missing_role_fail(self):
        with self.assertRaises(ValueError):
            harness.render_harness(FIXTURE_CONFIG, 'invented')
        with self.assertRaisesRegex(ValueError, 'canonical role'):
            harness.render_harness({'roles': {'missing': {}}}, 'codex')

    def test_legacy_opencode_version_reports_fallback(self):
        with patch.object(harness.shutil, 'which', return_value='/fixture/opencode'), patch.object(
                harness.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '1.0.0\n', '')):
            result = harness.probe_harness('opencode')
        self.assertEqual(result['status'], 'fallback')

    def test_native_role_permissions_follow_canonical_effects(self):
        outputs = harness.render_harness(FIXTURE_CONFIG, 'claude')
        self.assertIn('tools: Read, Grep, Glob, Edit, Write, Bash', outputs['.claude/agents/sdlc-engineer.md'])
        self.assertIn('tools: Read, Grep, Glob\n', outputs['.claude/agents/sdlc-reviewer.md'])
        opencode = harness.render_harness(FIXTURE_CONFIG, 'opencode')
        self.assertIn('action: edit', opencode['.opencode/agents/sdlc-reviewer.md'])
        codex = harness.render_harness(FIXTURE_CONFIG, 'codex')
        self.assertIn('shell_tool = false', codex['.codex/agents/sdlc-reviewer.toml'])
        limits = json.loads(codex['.sdlc/harness-codex.json'])
        self.assertFalse(limits['roles']['reviewer']['edit'])
        self.assertTrue(any('parent sandbox' in value for value in limits['limits']))

    def test_direct_provider_argv_and_environment_names(self):
        config = {**FIXTURE_CONFIG, 'integrations': {'github': {'enabled': True,
            'command': ['example-mcp', '--stdio'], 'args': ['--read-only'], 'env_from': ['GITHUB_TOKEN']}}}
        outputs = harness.render_harness(config, 'codex')
        self.assertIn('command = "example-mcp"', outputs['.codex/config.toml'])
        self.assertIn('args = ["--stdio", "--read-only"]', outputs['.codex/config.toml'])
        self.assertIn('env_vars = ["GITHUB_TOKEN"]', outputs['.codex/config.toml'])
        native = json.loads(harness.render_harness(config, 'opencode')['opencode.json'])
        self.assertEqual(native['mcp']['servers']['github']['command'], ['example-mcp', '--stdio', '--read-only'])
        self.assertEqual(native['mcp']['servers']['github']['environment']['GITHUB_TOKEN'], '{env:GITHUB_TOKEN}')

    def test_auto_selection_never_launches_provider_process(self):
        with patch.object(harness.shutil, 'which', return_value='/fixture/provider'), patch.object(
                harness.subprocess, 'run', side_effect=AssertionError('provider process launched')):
            self.assertEqual(harness.select_harnesses('auto', {}), ['codex'])

    def test_effective_workflow_and_scoped_deny_compile_to_native_denials(self):
        for overlay in ({'workflow': {'gates': {'external_writes': 'forbidden'}}},
                        {'policy': {'deny': ['external_write']}},
                        {'policy': {'deny': ['external_write:/workspace/api']}}):
            with self.subTest(overlay=overlay):
                config = {**FIXTURE_CONFIG, **overlay}
                project = {'path': '/workspace/api'}
                claude = harness.render_harness(config, 'claude', project)
                native = json.loads(claude['.claude/settings.json'])
                self.assertIn('Bash(git push *)', native['permissions']['deny'])
                self.assertNotIn('Bash(git push *)', native['permissions'].get('ask', []))
                self.assertIn('Effective external write policy: forbidden', claude['.sdlc/instructions.md'])
                cursor = json.loads(harness.render_harness(config, 'cursor', project)['.cursor/cli.json'])
                self.assertIn('Shell(git:push *)', cursor['permissions']['deny'])
                opencode = json.loads(harness.render_harness(config, 'opencode', project)['opencode.json'])
                self.assertIn({'action': 'shell', 'resource': 'git push *', 'effect': 'deny'}, opencode['permissions'])

    def test_project_effect_denials_bound_edits_shell_and_high_risk_commands(self):
        config = {**FIXTURE_CONFIG, 'policy': {'deny': ['local_edit', 'local_process', 'package_install', 'migration', 'infrastructure_change']}}
        claude = harness.render_harness(config, 'claude')
        denied = json.loads(claude['.claude/settings.json'])['permissions']['deny']
        for rule in ('Edit(*)', 'Write(*)', 'Bash(*)', 'Bash(npm install *)', 'Bash(terraform apply *)'):
            self.assertIn(rule, denied)
        self.assertIn('tools: Read, Grep, Glob\n', claude['.claude/agents/sdlc-engineer.md'])
        codex = harness.render_harness(config, 'codex')
        self.assertIn('sandbox_mode = "read-only"', codex['.codex/config.toml'])
        self.assertIn('shell_tool = false', codex['.codex/agents/sdlc-engineer.toml'])
        metadata = json.loads(codex['.sdlc/harness-codex.json'])
        self.assertEqual(metadata['effect_decisions']['migration']['decision'], 'forbidden')
        self.assertTrue(any('cannot express every effect denial' in note for note in metadata['limits']))
        import yaml
        opencode = harness.render_harness(config, 'opencode')
        header = opencode['.opencode/agents/sdlc-engineer.md'].split('---', 2)[1]
        self.assertIsInstance(yaml.safe_load(header)['permissions'], list)


class InstalledHarnessSmokeTests(unittest.TestCase):
    """Actual local CLI parsers; these never request a model response or external account."""
    def _native(self, name):
        import os
        import shutil
        executable = shutil.which(name)
        if executable is None:
            self.skipTest(f'{name} executable is unavailable')
        temporary = tempfile.TemporaryDirectory(prefix='sdlc-native-')
        self.addCleanup(temporary.cleanup)
        project = Path(temporary.name)
        role_root = project / 'canonical'
        (role_root / 'roles').mkdir(parents=True)
        (role_root / 'roles/engineer.md').write_text('---\nid: engineer\n---\nImplement the task and verify changes.\n')
        with patch.object(harness, 'KIT_ROOT', role_root):
            outputs = harness.render_harness({'roles': {'engineer': {'enabled': True}}, 'integrations': {}}, name)
        self.assertTrue(any('sdlc-engineer' in path for path in outputs))
        for relative, contents in outputs.items():
            path = project / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(contents)
        home = project / 'private-home'
        home.mkdir()
        env = {**os.environ, 'HOME': str(home), 'CODEX_HOME': str(project / '.codex'),
               'XDG_CONFIG_HOME': str(home / 'config'), 'XDG_DATA_HOME': str(home / 'data'),
               'XDG_STATE_HOME': str(home / 'state'), 'XDG_CACHE_HOME': str(home / 'cache')}
        return executable, project, env

    def test_installed_codex_reads_native_configuration(self):
        executable, project, env = self._native('codex')
        result = subprocess.run([executable, 'features', 'list'], cwd=project, env=env,
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.strip())

    def test_installed_claude_reads_native_settings(self):
        executable, project, env = self._native('claude')
        result = subprocess.run([executable, 'agents', '--json', '--settings', str(project / '.claude/settings.json'),
                                 '--setting-sources', 'project'], cwd=project, env=env,
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsInstance(json.loads(result.stdout), list)
