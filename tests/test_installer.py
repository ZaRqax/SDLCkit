"""Installer failure injection, ownership and reversibility contracts."""
import base64
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from sdlc import installer

CONFIG = {'schema_version': 2, 'agent': {'default_harness': 'codex'}, 'roles': {},
          'workflow': {'default': 'auto'}, 'integrations': {}}


def snapshot(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file() and not p.is_symlink()}


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='sdlc install ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'README.md').write_text('existing project')

    def install(self, **kwargs):
        return installer.install(self.root, harness='codex', config=copy.deepcopy(CONFIG), **kwargs)

    def test_dry_run_zero_files_or_directories(self):
        before = sorted(str(p) for p in self.root.rglob('*'))
        hashes = snapshot(self.root)
        report = self.install(dry_run=True)
        self.assertEqual(report['status'], 'preview')
        self.assertTrue(report['changes'])
        self.assertEqual(before, sorted(str(p) for p in self.root.rglob('*')))
        self.assertEqual(hashes, snapshot(self.root))

    def test_repeated_install_byte_identical_and_uninstall(self):
        self.assertEqual(self.install()['status'], 'installed')
        first = snapshot(self.root)
        again = self.install()
        self.assertEqual(again['changes'], [])
        self.assertEqual(again['operation_count'], 0)
        self.assertEqual(first, snapshot(self.root))
        self.assertEqual(installer.uninstall(self.root)['status'], 'uninstalled')
        self.assertEqual((self.root / 'README.md').read_text(), 'existing project')
        self.assertFalse((self.root / 'AGENTS.md').exists())

    def test_user_instructions_conflict_entire_install(self):
        agents = self.root / 'AGENTS.md'
        agents.write_text('my project rules\n')
        before = snapshot(self.root)
        report = self.install()
        self.assertEqual(report['status'], 'conflict')
        self.assertEqual(before, {k: v for k, v in snapshot(self.root).items() if k != '.sdlc/install.lock'})
        self.assertEqual(agents.read_text(), 'my project rules\n')
        self.assertFalse((self.root / '.codex').exists())

    def test_scoped_merge_idempotent_and_preserves_user_edits_on_uninstall(self):
        agents = self.root / 'AGENTS.md'
        original = 'my rules\n'
        agents.write_text(original)
        self.assertEqual(self.install(merge=True)['status'], 'installed')
        self.assertEqual(self.install(merge=True)['operation_count'], 0)
        agents.write_text('new user note\n' + agents.read_text())
        self.assertEqual(installer.uninstall(self.root)['status'], 'uninstalled')
        self.assertEqual(agents.read_text(), 'new user note\n' + original)

    def test_edit_owned_file_blocks_uninstall_and_reinstall(self):
        self.install()
        agents = self.root / 'AGENTS.md'
        agents.write_text(agents.read_text() + '\nmy edit\n')
        before = snapshot(self.root)
        self.assertEqual(installer.uninstall(self.root)['status'], 'conflict')
        self.assertEqual(self.install()['status'], 'conflict')
        self.assertEqual(snapshot(self.root), before)

    def test_user_config_not_merged_or_printed(self):
        path = self.root / '.codex'
        path.mkdir()
        (path / 'config.toml').write_text('token = "private-secret"')
        report = self.install(merge=True, dry_run=True)
        self.assertEqual(report['status'], 'conflict')
        self.assertNotIn('private-secret', json.dumps(report))

    def test_symlink_provider_folder_escape_rejected(self):
        with tempfile.TemporaryDirectory() as external:
            (self.root / '.codex').symlink_to(external, target_is_directory=True)
            with self.assertRaises(ValueError):
                self.install()
            self.assertEqual(list(Path(external).iterdir()), [])

    def test_symlink_state_escape_rejected(self):
        with tempfile.TemporaryDirectory() as external:
            (self.root / '.sdlc').symlink_to(external, target_is_directory=True)
            with self.assertRaises(ValueError):
                self.install(dry_run=True)
            self.assertEqual(list(Path(external).iterdir()), [])

    def test_path_traversal_rejected(self):
        for name in ('../escape', '/tmp/escape', 'a/../../escape'):
            with self.assertRaises(ValueError):
                installer.confined(self.root, name)

    def test_interrupted_transaction_rolls_back(self):
        original = installer._atomic_write
        calls = 0
        def fail_once(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise OSError('simulated disk interruption')
            return original(*args, **kwargs)
        with patch.object(installer, '_atomic_write', fail_once):
            with self.assertRaisesRegex(OSError, 'simulated'):
                self.install()
        self.assertFalse((self.root / 'AGENTS.md').exists())
        self.assertFalse((self.root / '.codex/config.toml').exists())
        self.assertFalse((self.root / installer.JOURNAL).exists())
        self.assertEqual(self.install()['status'], 'installed')

    def test_crash_journal_read_only_preview_then_recovery(self):
        state = self.root / '.sdlc'
        state.mkdir()
        (self.root / 'owned.txt').write_bytes(b'after')
        journal = {'schema_version': 1, 'operations': [{'path': 'owned.txt',
            'before': base64.b64encode(b'before').decode(), 'after': base64.b64encode(b'after').decode()}]}
        (self.root / installer.JOURNAL).write_text(json.dumps(journal))
        hashes = snapshot(self.root)
        self.assertEqual(installer.recover(self.root, True)['status'], 'recovery_required')
        self.assertEqual(snapshot(self.root), hashes)
        self.assertEqual(installer.recover(self.root)['status'], 'recovered')
        self.assertEqual((self.root / 'owned.txt').read_bytes(), b'before')

    def test_recovery_preserves_concurrent_user_edit(self):
        (self.root / '.sdlc').mkdir()
        (self.root / 'owned.txt').write_bytes(b'user edit')
        (self.root / installer.JOURNAL).write_text(json.dumps({'schema_version': 1, 'operations': [
            {'path': 'owned.txt', 'before': None, 'after': base64.b64encode(b'generated').decode()}]}))
        with self.assertRaises(installer.ConflictError):
            installer.recover(self.root)
        self.assertEqual((self.root / 'owned.txt').read_bytes(), b'user edit')

    def test_multiple_harnesses_partial_uninstall(self):
        report = installer.install(self.root, 'all', config=CONFIG)
        self.assertEqual(report['status'], 'installed')
        self.assertEqual(installer.uninstall(self.root, harness='codex')['status'], 'uninstalled')
        self.assertTrue((self.root / 'AGENTS.md').exists())
        self.assertTrue((self.root / '.claude/settings.json').exists())
        self.assertFalse((self.root / '.codex/config.toml').exists())
        self.assertEqual(installer.uninstall(self.root)['status'], 'uninstalled')
        self.assertFalse((self.root / 'AGENTS.md').exists())

    def test_declared_project_selection_limits_written_repositories(self):
        for name in ('selected', 'unselected'):
            (self.root / name).mkdir()
        config = copy.deepcopy(CONFIG)
        config['workspace'] = {'root': str(self.root), 'projects': [{'id': 'api', 'path': 'selected'}]}
        report = installer.install(self.root, 'codex', config=config)
        self.assertEqual(report['status'], 'installed')
        self.assertTrue((self.root / 'selected/AGENTS.md').exists())
        self.assertFalse((self.root / 'unselected/AGENTS.md').exists())
        self.assertEqual(installer.install(self.root, 'codex', config=config)['operation_count'], 0)

    def test_install_lock_prevents_second_writer(self):
        with installer._lock(self.root):
            with self.assertRaisesRegex(installer.ConflictError, 'another installation'):
                self.install()

    def test_explicit_effective_config_keeps_target_project_policy(self):
        from sdlc.config import load_config
        workspace = self.root / '.sdlc'
        workspace.mkdir()
        source = workspace / 'workspace.json'
        source.write_text(json.dumps({'schema_version': 2, 'workspace': {'root': str(self.root)}}))
        (workspace / 'project.yaml').write_text('schema_version: 2\nproject:\n  id: target\n  policy:\n    external_write: forbidden\n  generated_paths: ["generated/**"]\n')
        config = load_config(source)
        report = installer.install(self.root, 'claude', config=config, dry_run=True)
        self.assertEqual(report['status'], 'preview')
        settings = next(change['diff'] for change in report['changes'] if change['path'] == '.claude/settings.json')
        self.assertIn('+      "Bash(git push *)"', settings)
        self.assertIn('Edit(generated/**)', settings)
        generated = installer._render_plan(self.root, 'claude', 'generic', config)[0]
        native = json.loads(generated['.claude/settings.json']['content'])
        self.assertIn('Bash(git push *)', native['permissions']['deny'])
        self.assertNotIn('Bash(git push *)', native['permissions'].get('ask', []))
        self.assertIn('Edit(generated/**)', native['permissions']['deny'])
        saved_project = json.loads(generated['.sdlc/project.json']['content'])
        self.assertEqual(saved_project['project']['policy']['external_write'], 'forbidden')

    def test_fresh_install_persists_loadable_effective_source(self):
        from sdlc.config import load_for_target
        config = load_for_target(self.root)
        config['workflow']['default'] = 'investigation'
        config['integrations']['github']['enabled'] = True
        config['roles']['reviewer']['enabled'] = False
        report = installer.install(self.root, 'codex', config=config)
        self.assertEqual(report['status'], 'installed')
        self.assertTrue((self.root / '.sdlc/workspace.json').is_file())
        loaded = load_for_target(self.root)
        self.assertEqual(loaded['workflow']['default'], 'investigation')
        self.assertTrue(loaded['integrations']['github']['enabled'])
        self.assertFalse(loaded['roles']['reviewer']['enabled'])
        self.assertEqual(installer.install(self.root, 'codex')['operation_count'], 0)
        source = self.root / '.sdlc/workspace.json'
        source.write_text(source.read_text() + '\n')
        self.assertEqual(installer.install(self.root, 'codex')['status'], 'conflict')

    def test_existing_workspace_source_remains_user_owned(self):
        from sdlc.config import load_for_target
        state = self.root / '.sdlc'
        state.mkdir()
        source = state / 'workspace.yaml'
        original = 'schema_version: 2\nworkspace:\n  root: .\nworkflow:\n  default: investigation\n'
        source.write_text(original)
        result = installer.install(self.root, 'codex', config=load_for_target(self.root))
        self.assertEqual(result['status'], 'installed')
        self.assertEqual(source.read_text(), original)
        self.assertNotIn('.sdlc/workspace.yaml', installer._load_manifest(self.root)['files'])
        self.assertFalse((state / 'workspace.json').exists())

    def test_disjoint_allowlisted_projects_install_with_one_registry(self):
        from sdlc.config import load_for_target
        first = self.root / 'first'
        first.mkdir()
        with tempfile.TemporaryDirectory(prefix='sdlc external ') as external:
            second = Path(external)
            config = load_for_target(self.root)
            config['workspace']['allowed_paths'] = [str(second)]
            config['workspace']['projects'] = [{'id': 'first', 'path': str(first)}, {'id': 'second', 'path': str(second)}]
            result = installer.install(self.root, 'codex', config=config)
            self.assertEqual(result['status'], 'installed')
            self.assertTrue((first / 'AGENTS.md').is_file())
            self.assertFalse((second / 'AGENTS.md').exists())
            self.assertEqual(installer.install(second, 'codex', config=config)['status'], 'installed')
            self.assertTrue((second / 'AGENTS.md').is_file())
            self.assertEqual(installer.install(second, 'codex')['operation_count'], 0)
            self.assertEqual(load_for_target(second)['workspace']['root'], str(self.root))
