"""The active optional Go reviewer must work without a hosted microservice stack."""
from pathlib import Path
import tempfile
import unittest

from sdlc.config import ROOT, apply_profile, load_for_target


class GoProfileTests(unittest.TestCase):
    def test_active_reviewer_uses_actual_target_contracts(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            (target / 'go.mod').write_text('module example.test/library\n\ngo 1.22\n')
            config = apply_profile(load_for_target(target), 'go')
            self.assertTrue(config['roles']['go-reviewer']['enabled'])
            self.assertTrue(all(not command.startswith('task ') for commands in config['project']['commands'].values()
                                for command in commands))
        guide = (ROOT / 'profiles/go/reviewer.md').read_text()
        for forbidden in ('origin/develop', 'git fetch origin', 'task lint', 'task test', 'Acme',
                          'specs/$1', 'AGENTS.md §', 'model: opus'):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, guide)
        for required in ('local Git metadata', 'actual project commands', 'Self-refutation', 'confidence',
                         'Concurrency', 'resources', 'acceptance criteria', 'unavailable'):
            with self.subTest(required=required):
                self.assertIn(required.lower(), guide.lower())
        role = (ROOT / 'roles/go-reviewer.md').read_text()
        self.assertIn('`profiles/go/reviewer.md`', role)
        self.assertNotIn('profiles/acme-go', role)
        historical = (ROOT / 'profiles/acme-go/reviewer.md').read_text()
        self.assertIn('git fetch origin develop', historical)


if __name__ == '__main__':
    unittest.main()
