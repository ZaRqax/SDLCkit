"""Preserved setup entry points run only in disposable copies and private homes."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class LegacySetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='sdlc legacy ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'kit copy'
        self.root.mkdir()
        shutil.copy2(ROOT / 'setup.sh', self.root / 'setup.sh')
        shutil.copytree(ROOT / 'agents-config', self.root / 'agents-config')
        shutil.copytree(ROOT / 'templates', self.root / 'templates')
        (self.root / 'scripts').mkdir()
        for name, body in {'check-kit.sh': 'echo verifier-dispatched\n', 'apply-pipeline.sh': 'echo pipeline-dispatched\n'}.items():
            (self.root / 'scripts' / name).write_text('#!/bin/bash\n' + body)
        (self.root / 'scripts/render-harness.py').write_text('import json,sys\nprint(json.dumps(sys.argv[1:]))\n')
        for name in ('pi', 'qwen', 'opencode'):
            porter = self.root / 'agents-config' / name / {'pi': 'port-agents.py', 'qwen': 'port-to-qwen.py',
                                                        'opencode': 'port-to-opencode.py'}[name]
            porter.write_text('import pathlib,sys\np=pathlib.Path(sys.argv[1]);p.mkdir(parents=True,exist_ok=True)\n')
        (self.root / '.env.example').write_text('# no secrets or mandatory integration\n')
        (self.root / 'CLAUDE.md').write_text('@AGENTS.md\n')
        (self.root / 'AGENTS.md').write_text('project rules\n')
        (self.root / 'QWEN.md').write_text('@AGENTS.md\n')
        (self.root / '.githooks').mkdir()
        (self.root / '.githooks/pre-commit').write_text('#!/bin/sh\nexit 0\n')
        (self.root / '.claude/hooks').mkdir(parents=True)
        (self.root / '.claude/hooks/fixture.sh').write_text('#!/bin/sh\nexit 0\n')
        (self.root / '.mcp.json').write_text('{"mcpServers":{}}')
        bindir = Path(self.temp.name) / 'bin'
        bindir.mkdir()
        self.marker = Path(self.temp.name) / 'package-called'
        for name in ('pi', 'omp'):
            path = bindir / name
            path.write_text('#!/bin/sh\nif [ "$1" = install ]; then touch "$PACKAGE_MARKER"; fi\necho fixture\n')
            path.chmod(0o755)
        self.env = {**os.environ, 'HOME': str(Path(self.temp.name) / 'private home'),
                    'SDLC_KIT_STATE_DIR': str(Path(self.temp.name) / 'state'),
                    'PI_CODING_AGENT_DIR': str(Path(self.temp.name) / 'pi dir'),
                    'PATH': str(bindir) + os.pathsep + os.environ['PATH'], 'PACKAGE_MARKER': str(self.marker)}
        Path(self.env['HOME']).mkdir()
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)

    def run_setup(self, *args):
        return subprocess.run(['bash', str(self.root / 'setup.sh'), *args], cwd=self.root,
                              env=self.env, capture_output=True, text=True, timeout=30)

    def test_check_pipeline_list_and_help_dispatch(self):
        self.assertIn('verifier-dispatched', self.run_setup('--check').stdout)
        self.assertIn('pipeline-dispatched', self.run_setup('--pipeline').stdout)
        self.assertEqual(self.run_setup('--list-installed').returncode, 0)
        self.assertIn('--help', self.run_setup('--help').stdout)
        self.assertFalse((self.root / '.env').exists())

    def test_all_preserved_positional_invocations(self):
        for name in ('pi', 'qwen', 'crush', 'opencode', 'claude', 'omp'):
            with self.subTest(harness=name):
                result = self.run_setup(name)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.marker.exists(), 'legacy setup must not install packages without explicit grant')

    def test_explicit_package_install_grant(self):
        result = self.run_setup('pi', '--allow-package-installs')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(self.marker.exists())

    def test_target_flags_bypass_all_global_legacy_mutations(self):
        result = self.run_setup('--target', str(Path(self.temp.name) / 'project path'), '--harness', 'codex', '--dry-run')
        self.assertEqual(result.returncode, 0)
        parsed = json.loads(result.stdout)
        self.assertIn('codex', parsed)
        self.assertIn('--dry-run', parsed)
        self.assertFalse((self.root / '.env').exists())
        self.assertFalse(Path(self.env['SDLC_KIT_STATE_DIR']).exists())
        self.assertEqual(list(Path(self.env['HOME']).iterdir()), [])

    def test_legacy_backup_reverse_uninstall_and_user_edit_conflict(self):
        existing = self.root / 'crush.json'
        existing.write_text('my original configuration')
        self.assertEqual(self.run_setup('crush').returncode, 0)
        generated = existing.read_bytes()
        self.assertEqual(self.run_setup('crush').returncode, 0)
        existing.write_bytes(generated + b'\nuser edit')
        failed = self.run_setup('--uninstall', 'crush')
        self.assertEqual(failed.returncode, 1)
        self.assertIn('user edits preserved', failed.stdout)
        self.assertTrue(existing.read_bytes().endswith(b'user edit'))
        existing.write_bytes(generated)
        restored = self.run_setup('--uninstall', 'crush')
        self.assertEqual(restored.returncode, 0, restored.stdout + restored.stderr)
        self.assertEqual(existing.read_text(), 'my original configuration')
        self.assertTrue((self.root / '.env').exists())

    def test_old_five_column_manifest_still_uninstalls(self):
        state = Path(self.env['SDLC_KIT_STATE_DIR']); state.mkdir()
        created = self.root / 'legacy-created.txt'; created.write_text('fixture')
        (state / 'manifest.tsv').write_text(f'old\tclaude\tcreated\t{created}\t-\n')
        result = self.run_setup('--uninstall', 'claude')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(created.exists())
