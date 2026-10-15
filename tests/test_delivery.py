import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from sdlc import delivery
from sdlc.storage import atomic_json


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null"})
        environment.start()
        self.addCleanup(environment.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.git("init", "-b", "trunk")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "core.hooksPath", "/dev/null")
        (self.repo / ".gitignore").write_text(".sdlc/\n")
        (self.repo / "app.txt").write_text("before\n")
        self.git("add", ".")
        self.git("commit", "-m", "initial")
        self.git("switch", "-c", "work/test")
        self.config = {"integrations": {"github": {"enabled": True}, "gitlab": {"enabled": True}}}

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], capture_output=True, check=True).stdout

    def test_patch_contains_staged_unstaged_and_untracked_without_remote_calls(self):
        (self.repo / "app.txt").write_text("after\n")
        (self.repo / "new.txt").write_text("new file\n")
        self.git("add", "app.txt")
        prepared = delivery.prepare(self.repo, "patch", "work-test")
        original = delivery.command

        def checked(argv, **kwargs):
            self.assertNotIn(argv[0], {"gh", "glab"})
            self.assertNotIn("push", argv)
            return original(argv, **kwargs)

        with patch("sdlc.delivery.authorize"), patch("sdlc.delivery.command", side_effect=checked):
            result = delivery.publish(prepared, output="result.patch", approved_local=True)
        data = Path(result["path"]).read_text()
        self.assertIn("+after", data)
        self.assertIn("+new file", data)
        self.git("apply", "--reverse", "--check", "result.patch")

    def test_stale_preparation_rejected(self):
        (self.repo / "app.txt").write_text("change\n")
        prepared = delivery.prepare(self.repo, "patch", "work-test")
        (self.repo / "app.txt").write_text("new change\n")
        with self.assertRaisesRegex(ValueError, "stale"):
            delivery.validate(prepared)

    def test_committed_worker_changes_can_be_exported_from_explicit_baseline(self):
        baseline = self.git("rev-parse", "HEAD").decode().strip()
        (self.repo / "app.txt").write_text("committed change\n")
        self.git("add", "app.txt")
        self.git("commit", "-m", "worker change")
        prepared = delivery.prepare(self.repo, "patch", "work-snapshot", since=baseline)
        with patch("sdlc.delivery.authorize"):
            result = delivery.publish(prepared, output="snapshot.patch", approved_local=True)
        self.assertIn("+committed change", Path(result["path"]).read_text())
        self.git("apply", "--reverse", "--check", "snapshot.patch")

    def test_secrets_and_internal_state_cannot_be_delivered(self):
        for name in (".env", ".sdlc/runs/state.json"):
            with self.assertRaises(PermissionError):
                delivery.prepare(self.repo, "patch", "work-test", paths=[name])

    def test_local_commit_only_selected_files_and_reconciles(self):
        (self.repo / "app.txt").write_text("change\n")
        (self.repo / "other.txt").write_text("user work\n")
        prepared = delivery.prepare(self.repo, "commit", "work-test", paths=["app.txt"])
        with patch("sdlc.delivery.authorize"):
            result = delivery.publish(prepared, approved_local=True)
            self.assertEqual(delivery.publish(prepared, approved_local=True), result)
        self.assertEqual(self.git("show", "--pretty=", "--name-only", "HEAD").decode().strip(), "app.txt")
        self.assertTrue((self.repo / "other.txt").exists())

    def test_index_is_preserved_when_not_empty(self):
        (self.repo / "app.txt").write_text("change\n")
        self.git("add", "app.txt")
        prepared = delivery.prepare(self.repo, "commit", "work-test")
        with patch("sdlc.delivery.authorize"):
            with self.assertRaisesRegex(ValueError, "empty index"):
                delivery.publish(prepared, approved_local=True)
        self.assertEqual(self.git("diff", "--cached", "--name-only").decode().strip(), "app.txt")

    def test_local_branch_does_not_require_tracker_or_remote(self):
        (self.repo / "app.txt").write_text("change\n")
        prepared = delivery.prepare(self.repo, "local_branch", "work-local")
        with patch("sdlc.delivery.authorize"):
            result = delivery.publish(prepared, approved_local=True)
        self.assertEqual(result["branch"], "work/work-local")

    def test_remote_disabled_and_missing_approval_do_not_publish(self):
        self.git("remote", "add", "origin", "https://github.com/example/project.git")
        prepared = delivery.prepare(self.repo, "github_pr", "work-test", base="trunk")
        with patch("sdlc.delivery.authorize", side_effect=PermissionError("approval required")):
            with patch("sdlc.delivery.reconcile") as reconcile:
                with self.assertRaises(PermissionError):
                    delivery.publish(prepared, config=self.config)
                reconcile.assert_not_called()

    def test_reconcile_existing_remote_marker_does_not_push(self):
        self.git("remote", "add", "origin", "https://github.com/example/project.git")
        prepared = delivery.prepare(self.repo, "github_pr", "work-test", base="trunk")
        original = delivery.command

        def fake(argv, **kwargs):
            if argv[0] == "gh":
                return json.dumps([{"url": "https://github.com/example/project/pull/1", "body": prepared["marker"], "state": "OPEN", "headRefOid": prepared["revision"]}]).encode()
            self.assertNotIn("push", argv)
            return original(argv, **kwargs)

        with patch("sdlc.delivery.authorize"), patch("sdlc.delivery.command", side_effect=fake):
            result = delivery.publish(prepared, config=self.config, approved_external=True)
        self.assertTrue(result["reconciled"])

    def test_ambiguous_publication_never_creates_duplicate(self):
        self.git("remote", "add", "origin", "https://github.com/example/project.git")
        prepared = delivery.prepare(self.repo, "github_pr", "work-test", base="trunk")
        record = delivery.metadata_root(self.repo) / "sdlckit/deliveries" / (prepared["idempotency_key"] + ".json")
        atomic_json(record, {"status": "ambiguous", "prepared": prepared})
        with patch("sdlc.delivery.authorize"), patch("sdlc.delivery.reconcile", return_value=None):
            with self.assertRaisesRegex(ValueError, "ambiguous"):
                delivery.publish(prepared, config=self.config, approved_external=True)

    def test_provider_publish_uses_body_file_and_reconciles_repeated_delivery(self):
        self.git("remote", "add", "origin", "https://github.com/example/project.git")
        for kind, remote in (("github_pr", "https://github.com/example/project.git"),
                             ("gitlab_mr", "https://git.example.invalid/team/project.git")):
            with self.subTest(kind=kind):
                self.git("remote", "set-url", "origin", remote)
                prepared = delivery.prepare(self.repo, kind, "work-" + kind, title="Review", body="Line one\nLiteral $(text)\n", base="trunk")
                original = delivery.command
                calls, created = [], []

                def fake(argv, **kwargs):
                    if argv[0] == "git" and "push" in argv:
                        calls.append("push")
                        return b""
                    if argv[0] in {"gh", "glab"}:
                        if "create" in argv:
                            flag = "--body-file" if argv[0] == "gh" else "--description-file"
                            content = Path(argv[argv.index(flag) + 1]).read_text()
                            self.assertIn("Line one\nLiteral $(text)", content)
                            self.assertIn(prepared["marker"], content)
                            self.assertIn("--draft", argv)
                            created.append(argv[0])
                            return b""
                        value = [{"url": "https://example.invalid/review/1", "web_url": "https://example.invalid/review/1",
                                  "body": prepared["marker"], "description": prepared["marker"], "state": "opened",
                                  "headRefOid": prepared["revision"], "sha": prepared["revision"]}] if created else []
                        return json.dumps(value).encode()
                    return original(argv, **kwargs)

                with patch("sdlc.delivery.authorize"), patch("sdlc.delivery.command", side_effect=fake):
                    result = delivery.publish(prepared, config=self.config, approved_external=True)
                    again = delivery.publish(prepared, config=self.config, approved_external=True)
                self.assertEqual(result, again)
                self.assertEqual(len(created), 1)
                self.assertEqual(calls, ["push"])

    def test_git_pathspec_magic_cannot_expand_to_secret_files(self):
        (self.repo / ".env").write_text("PRIVATE=hidden\n")
        self.git("add", ".env")
        self.git("commit", "-m", "fixture secret")
        (self.repo / ".env").write_text("PRIVATE=changed\n")
        with self.assertRaises(ValueError):
            delivery.prepare(self.repo, "patch", "work-magic", paths=[":(glob)**"])

    def test_committed_secret_history_is_audited_before_publication(self):
        (self.repo / ".env").write_text("PRIVATE=hidden\n")
        self.git("add", ".env")
        self.git("commit", "-m", "fixture secret")
        self.git("rm", ".env")
        self.git("commit", "-m", "remove fixture secret")
        with self.assertRaises(PermissionError):
            delivery.prepare(self.repo, "github_pr", "work-secret", base="trunk")

    def test_new_change_cannot_be_reported_as_previous_local_commit(self):
        (self.repo / "app.txt").write_text("first\n")
        prepared = delivery.prepare(self.repo, "commit", "work-reused")
        with patch("sdlc.delivery.authorize"):
            delivery.publish(prepared)
            (self.repo / "app.txt").write_text("second\n")
            new_prepared = delivery.prepare(self.repo, "commit", "work-reused")
            with self.assertRaisesRegex(ValueError, "different local change"):
                delivery.publish(new_prepared)

    def test_secret_content_is_rejected_even_under_generic_filename(self):
        (self.repo / "notes.txt").write_text("-----BEGIN " + "PRIVATE KEY-----\nprivate-data\n")
        with self.assertRaises(PermissionError):
            delivery.prepare(self.repo, "patch", "work-secret-content")

    def test_publication_pushes_prepared_hash_even_when_local_head_changes(self):
        self.git("remote", "add", "origin", "https://github.com/example/project.git")
        prepared = delivery.prepare(self.repo, "github_pr", "work-pinned", base="trunk")
        original = delivery.command
        calls, created = [], []

        def fake(argv, **kwargs):
            if argv[0] == 'git' and 'push' in argv:
                calls.append(argv[-1])
                return b''
            if argv[0] == 'gh':
                if 'create' in argv:
                    created.append(True)
                    return b''
                if not calls:
                    (self.repo / 'app.txt').write_text('later local work\n')
                    self.git('add', 'app.txt')
                    self.git('commit', '-m', 'unprepared local revision')
                rows = [{'url': 'https://github.com/example/project/pull/1', 'body': prepared['marker'],
                         'state': 'OPEN', 'headRefOid': prepared['revision']}] if created else []
                return json.dumps(rows).encode()
            return original(argv, **kwargs)

        with patch('sdlc.delivery.authorize'), patch('sdlc.delivery.command', side_effect=fake):
            result = delivery.publish(prepared, config=self.config, approved_external=True)
        self.assertEqual(calls, [prepared['revision'] + ':refs/heads/work/test'])
        self.assertEqual(result['revision'], prepared['revision'])
        self.assertNotEqual(self.git('rev-parse', 'HEAD'), prepared['revision'])


if __name__ == "__main__":
    unittest.main()
