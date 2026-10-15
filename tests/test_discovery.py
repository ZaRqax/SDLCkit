"""Disposable repository discovery without executing project code."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from sdlc.discovery import discover_workspace


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='sdlc discovery ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def repo(self, name):
        path = self.root / name
        path.mkdir()
        subprocess.run(['git', 'init', '-q', str(path)], check=True)
        return path

    def test_mixed_repositories_commands_and_secret_exclusion(self):
        go = self.repo('go api')
        (go / 'go.mod').write_text('module example.com/api\n\ngo 1.23\n')
        (go / 'Taskfile.yml').write_text('version: "3"\ntasks:\n  test:\n    cmds: [go test ./...]\n  fmt:\n    cmds: [gofmt -w .]\n')
        py = self.repo('python')
        (py / 'pyproject.toml').write_text('[project]\nname="sample"\n[tool.pytest.ini_options]\n')
        (py / 'tests').mkdir()
        (py / 'tests/test_api.py').write_text('raise RuntimeError("must never execute")')
        (py / '.env').write_text('TOKEN=must-not-read')
        (py / 'AGENTS.md').write_text('Keep my conventions')
        ts = self.repo('ui')
        (ts / 'package.json').write_text(json.dumps({'scripts': {'test': 'throw error', 'lint': 'eslint .'}}))
        (ts / 'tsconfig.json').write_text('{}')
        report = discover_workspace(self.root)
        self.assertEqual(len(report['projects']), 3)
        projects = {p['id']: p for p in report['projects']}
        self.assertEqual(projects['go-api']['languages'], ['go'])
        self.assertIn('task test', projects['go-api']['commands']['test'])
        self.assertEqual(projects['python']['commands']['test'], ['python3 -m pytest'])
        self.assertIn('AGENTS.md', projects['python']['instructions'])
        self.assertEqual(projects['ui']['languages'], ['typescript'])
        self.assertNotIn('must-not-read', json.dumps(report))
        self.assertTrue(report['read_only'])

    def test_no_git_no_remote_fallback(self):
        (self.root / 'requirements.txt').write_text('')
        report = discover_workspace(self.root)
        self.assertEqual(len(report['projects']), 1)
        self.assertEqual(report['projects'][0]['kind'], 'directory')
        self.assertEqual(report['projects'][0]['git']['remotes'], {})

    def test_nested_repos_and_symlinks(self):
        parent = self.repo('parent')
        nested = parent / 'nested'
        subprocess.run(['git', 'init', '-q', str(nested)], check=True)
        (self.root / 'link').symlink_to(parent, target_is_directory=True)
        report = discover_workspace(self.root)
        self.assertEqual(len(report['projects']), 2)
        self.assertEqual(report['skipped_symlinks'], [str(self.root / 'link')])

    def test_linked_worktree(self):
        repo = self.repo('main')
        (repo / 'README.md').write_text('fixture')
        subprocess.run(['git', '-C', str(repo), 'add', '.'], check=True)
        subprocess.run(['git', '-C', str(repo), '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.test',
                        'commit', '-qm', 'fixture'], check=True)
        worktree = self.root / 'separate worktree'
        subprocess.run(['git', '-C', str(repo), 'worktree', 'add', '-q', '-b', 'work', str(worktree)], check=True)
        report = discover_workspace(self.root)
        found = next(p for p in report['projects'] if p['path'] == str(worktree))
        self.assertTrue(found['git']['worktree'])

    def test_secret_files_never_opened(self):
        secret = self.root / '.env'
        secret.write_text('PRIVATE=secret')
        original = Path.open
        def guarded(path, *args, **kwargs):
            if path.name == '.env':
                raise AssertionError('secret opened')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'open', guarded):
            discover_workspace(self.root)

    def test_remote_credentials_redacted(self):
        repo = self.repo('repo')
        subprocess.run(['git', '-C', str(repo), 'remote', 'add', 'origin',
                        'https://user:private-token@example.test/group/repo?secret=hidden'], check=True)
        report = discover_workspace(self.root)
        self.assertEqual(report['projects'][0]['git']['remotes']['origin'], 'https://example.test/group/repo')
        self.assertNotIn('private-token', json.dumps(report))

    def test_local_submodule_gitfile_is_discovered(self):
        source = self.repo('module-source')
        (source / 'README.md').write_text('submodule fixture')
        subprocess.run(['git', '-C', str(source), 'add', '.'], check=True)
        subprocess.run(['git', '-C', str(source), '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.test',
                        'commit', '-qm', 'fixture'], check=True)
        parent = self.repo('parent-with-module')
        subprocess.run(['git', '-c', 'protocol.file.allow=always', '-C', str(parent), 'submodule', 'add', '-q',
                        str(source), 'components/module'], check=True)
        report = discover_workspace(parent)
        submodule = next(project for project in report['projects'] if project['id'] == 'components-module')
        self.assertTrue(submodule['git']['submodule'])
