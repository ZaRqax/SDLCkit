"""Effect authorization remains independent of provider power and source text."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from sdlc.policy import classify_command, evaluate_effect, generated_path, require_effect, secret_path


class PolicyTests(unittest.TestCase):
    def test_local_artifacts_do_not_require_publication_authority(self):
        for effect in ('observe', 'read', 'local_write', 'test', 'patch', 'commit', 'local_branch', 'report'):
            with self.subTest(effect=effect):
                self.assertEqual(require_effect(effect)['decision'], 'allow')

    def test_remote_effects_need_scoped_authority_and_deny_wins(self):
        self.assertEqual(evaluate_effect('external_write')['decision'], 'approval_required')
        with self.assertRaises(PermissionError):
            require_effect('github_pr')
        require_effect('external_write', approved={'effects': ['external_write'], 'scopes': ['/repo']}, scope='/repo')
        with self.assertRaises(PermissionError):
            require_effect('external_write', approved={'effects': ['external_write'], 'scopes': ['/repo']}, scope='/other')
        with self.assertRaises(PermissionError):
            require_effect('push', {'policy': {'deny': ['push']}}, approved=True)
        with self.assertRaises(PermissionError):
            require_effect('external_write', {'policy': {'external_write': 'forbidden'}}, approved=True)

    def test_forbidden_and_unknown_effects_cannot_be_approved(self):
        for effect in ('force_push', 'auto_merge', 'merge', 'deploy', 'secret_read', 'destructive', 'invented'):
            with self.subTest(effect=effect):
                self.assertEqual(evaluate_effect(effect, approved=True)['decision'], 'forbidden')

    def test_direct_command_effects_and_safe_cleanup(self):
        commands = {
            'git push origin work/example': 'push',
            'git -C repo push --force origin main': 'force_push',
            'gh pr create --body-file body.md': 'external_write',
            'glab mr merge 1': 'merge',
            'terraform destroy': 'destructive',
            'cat .env.local': 'secret_read',
            'cat .env.example': 'local_process',
            'psql -c "DROP DATABASE sample"': 'destructive',
            'rm -rf /': 'destructive',
            'rm -rf "$HOME"': 'destructive',
            'rm -rf /tmp/build-artifact': 'local_process',
            'python3 -m unittest': 'local_process',
            'npm install some-package': 'package_install',
            'curl -X POST https://example.test': 'external_write',
        }
        for command, effect in commands.items():
            with self.subTest(command=command):
                self.assertEqual(classify_command(command), effect)

    def test_secret_paths_preserve_examples_and_public_keys(self):
        for path in ('.env', '/repo/.env.production', '/home/example/.ssh/id_ed25519',
                     '/home/example/.aws/credentials', 'credentials.json'):
            self.assertTrue(secret_path(path), path)
        for path in ('.env.example', '.env.sample', '/repo/config.py', '/home/example/.ssh/id_ed25519.pub'):
            self.assertFalse(secret_path(path), path)

    def test_generated_paths_come_from_target_profile(self):
        config = {'project': {'path': '/repo', 'generated_paths': ['src/generated/**', '**/*.pb.go']}}
        self.assertTrue(generated_path('/repo/src/generated/a/file.py', config))
        self.assertTrue(generated_path('/repo/a.pb.go', config))
        self.assertFalse(generated_path('/repo/mocks/owned.py', config))
        self.assertFalse(generated_path('/repo/src/generated.py', config))

    def test_hook_blocks_destructive_and_project_generated_paths(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            (target / '.sdlc').mkdir()
            (target / '.sdlc/project.json').write_text(json.dumps({'schema_version': 2,
                'project': {'id': 'fixture', 'generated_paths': ['src/generated/**']}}))
            for mode, tool_input in [('pre-bash', {'command': 'terraform destroy'}),
                                     ('pre-edit', {'file_path': str(target / 'src/generated/a.py')})]:
                result = subprocess.run([sys.executable, '-m', 'sdlc.policy', mode], cwd=root,
                      input=json.dumps({'cwd': directory, 'tool_input': tool_input}), text=True, capture_output=True)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn('BLOCKED', result.stderr)
            result = subprocess.run([sys.executable, '-m', 'sdlc.policy', 'pre-bash'], cwd=root,
                input=json.dumps({'cwd': directory, 'tool_input': {'command': 'git push origin work/example'}}),
                text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['hookSpecificOutput']['permissionDecision'], 'ask')


if __name__ == '__main__':
    unittest.main()
