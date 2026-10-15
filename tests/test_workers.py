from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import time
import unittest

from sdlc.runtime import Store
from sdlc.workers import Coordinator, validate_argv
from test_runtime import context, python, quick_recipe, repository


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="sdlc-workers-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root / "state" / "runtime.db")
        self.repo = repository(self.root / "repo")

    def test_independent_same_repo_workers_are_concurrent_and_isolated(self):
        self._concurrent([self.repo, self.repo])

    def test_independent_repositories_run_concurrently(self):
        self._concurrent([self.repo, repository(self.root / "second")])

    def _concurrent(self, repos):
        cross_repo = len(set(repos)) > 1
        run = self.store.create_run("parallel", quick_recipe(cross_repo), context(cross_repo))
        for number, repo in enumerate(repos):
            other = self.root / f"started-{1-number}"
            own = self.root / f"started-{number}"
            code = (f"import time; from pathlib import Path; p=Path({str(own)!r}); p.touch(); "
                    f"other=Path({str(other)!r}); end=time.monotonic()+5\n"
                    "while not other.exists() and time.monotonic()<end: time.sleep(.01)\n"
                    "assert other.exists(), 'workers did not overlap'\n"
                    f"Path('change-{number}').write_text('isolated')")
            self.store.add_task(run, f"writer-{number}", repo, python(code))
        # Verify both outputs by taking their independent heads into separate check worktrees.
        for number, repo in enumerate(repos):
            check = f"from pathlib import Path; assert Path('change-{number}').read_text() == 'isolated'"
            if number == 1:
                check += ("; import os,json; dependencies=json.loads(os.environ['SDLC_DEPENDENCIES']); "
                          "assert all((Path(item['worktree']) / ('change-'+name[-1])).read_text() == 'isolated' "
                          "for name,item in dependencies.items())")
            self.store.add_task(run, f"verify-{number}", repo, python(check), kind="verify",
                                needs=["writer-0", "writer-1"], integration=number == 1)
        if cross_repo:
            self.store.add_task(run, "aggregate-review", repos[0], python(
                "import os,json; from pathlib import Path; "
                "assert len(json.loads(os.environ['SDLC_DEPENDENCIES'])) == 2; "
                "Path(os.environ['SDLC_RESULT_PATH']).write_text(json.dumps({'passed':True,'findings':[]}))"),
                kind="review", needs=["verify-0", "verify-1"])
        self.assertEqual(Coordinator(self.store, max_workers=2).run(run, approved_local=True)["state"], "verified")
        tasks = self.store.tasks(run)
        trees = [t["result"]["worktree"] for t in tasks]
        self.assertEqual(len(trees), len(set(trees)))
        self.assertFalse((self.repo / "change-0").exists())
        for task in tasks:
            self.assertNotEqual(task["result"]["worktree"], str(task["spec"]["repo"]))

    def test_timeout_log_and_disk_budgets_fail_honestly(self):
        cases = [("timeout", "import time; time.sleep(3)", {"timeout": .15}),
                 ("log", "print('x'*100000)", {"max_log_bytes": 1024}),
                 ("disk", "from pathlib import Path; Path('large').write_bytes(b'x'*100000)", {"max_disk_bytes": 4096})]
        for name, code, limits in cases:
            with self.subTest(name=name):
                run = self.store.create_run(name, {"stages": [{"id": "execute"}]}, context())
                self.store.add_task(run, "worker", self.repo, python(code), **limits)
                self.assertEqual(Coordinator(self.store).run(run, approved_local=True)["state"], "failed")
                evidence = self.store.tasks(run)[0]["result"]
                self.assertIn("budget exceeded", evidence["error"])
                if name == "log":
                    self.assertLessEqual(Path(evidence["log"]).stat().st_size, 1024)

    def test_cancel_running_worker_and_process_group(self):
        marker = self.root / "cancel-first"
        run = self.store.create_run("cancel", quick_recipe(), context())
        self.store.add_task(run, "long", self.repo, python(
            f"import time; from pathlib import Path; p=Path({str(marker)!r}); old=p.exists(); p.touch(); "
            "time.sleep(0 if old else 30)"), max_attempts=2)
        self.store.add_task(run, "checks", self.repo, python("print('retry verified')"), kind="verify", needs=["long"])
        coordinator = Coordinator(self.store)
        with ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(coordinator.run, run, True)
            end = time.monotonic() + 5
            while not self.store.tasks(run)[0]["pid"] and time.monotonic() < end:
                time.sleep(.02)
            self.assertIsNotNone(self.store.tasks(run)[0]["pid"])
            self.store.cancel(run)
            self.assertEqual(result.result(timeout=6)["state"], "cancelled")
        self.assertEqual(self.store.tasks(run)[0]["state"], "cancelled")
        self.store.retry(run, "long")
        self.assertEqual(Coordinator(self.store).run(run, approved_local=True)["state"], "verified")
        self.assertEqual(self.store.tasks(run)[0]["attempts"], 2)

    def test_real_subprocess_crash_is_recoverable_with_retry(self):
        marker = self.root / "crashed"
        run = self.store.create_run("actual-crash", quick_recipe(), context())
        code = (f"import os; from pathlib import Path; p=Path({str(marker)!r}); "
                "old=p.exists(); p.touch(); os._exit(0 if old else 19)")
        self.store.add_task(run, "worker", self.repo, python(code), max_attempts=2)
        self.store.add_task(run, "checks", self.repo, python("pass"), needs=["worker"], kind="verify")
        self.assertEqual(Coordinator(self.store).run(run, approved_local=True)["state"], "failed")
        self.assertEqual(self.store.tasks(run)[0]["result"]["exit_code"], 19)
        self.store.retry(run, "worker")
        self.assertEqual(Coordinator(Store(self.store.path)).run(run, approved_local=True)["state"], "verified")

    def test_input_revision_is_frozen_and_source_head_drift_not_imported(self):
        from sdlc.workers import git
        run = self.store.create_run("frozen", quick_recipe(), context())
        self.store.add_task(run, "worker", self.repo, python("from pathlib import Path; assert not Path('later').exists()"))
        self.store.add_task(run, "checks", self.repo, python("pass"), needs=["worker"], kind="verify")
        recorded = self.store.tasks(run)[0]["spec"]["input_revision"]
        (self.repo / "later").write_text("source changed since plan")
        git(self.repo, "add", "later")
        git(self.repo, "commit", "-m", "unrelated later change")
        self.assertNotEqual(recorded, git(self.repo, "rev-parse", "HEAD"))
        self.assertEqual(Coordinator(self.store).run(run, approved_local=True)["state"], "verified")
        self.assertEqual(self.store.tasks(run)[0]["result"]["input_revision"], recorded)

    def test_snapshot_rejects_secret_and_configured_generated_paths(self):
        for name in [".env", "key.pem", "credentials.json", "internal/generated.py"]:
            with self.subTest(path=name):
                if name.startswith("internal/"):
                    profile = self.repo / ".sdlc" / "project.json"
                    profile.parent.mkdir(exist_ok=True)
                    profile.write_text(json.dumps({"schema_version": 2, "project": {"generated_paths": ["internal/generated.py"]}}))
                run = self.store.create_run("secret-rejection", {"stages": [{"id": "execute"}]}, context())
                code = f"from pathlib import Path; p=Path({name!r}); p.parent.mkdir(exist_ok=True); p.write_text('sensitive')"
                self.store.add_task(run, "worker", self.repo, python(code))
                self.assertEqual(Coordinator(self.store).run(run, approved_local=True)["state"], "failed")
                self.assertIn("snapshot refuses", self.store.tasks(run)[0]["result"]["error"])

    def test_effect_denial_applies_project_policy_and_direct_command_classification(self):
        profile = self.repo / ".sdlc" / "project.json"
        profile.parent.mkdir()
        profile.write_text(json.dumps({"schema_version": 2, "project": {"policy": {"deny": ["local_write"]}}}))
        run = self.store.create_run("denied-local", {"stages": [{"id": "execute"}]}, context())
        self.store.add_task(run, "worker", self.repo, python("raise SystemExit('must not launch')"))
        with self.assertRaises(PermissionError):
            Coordinator(self.store).run(run, approved_local=True)
        profile.unlink()
        for number, command in enumerate([["git", "push", "origin", "HEAD"], ["pip", "install", "sample"],
                                           ["curl", "-X", "POST", "https://example.invalid"], ["terraform", "destroy"]]):
            run = self.store.create_run(f"denied-{number}", {"stages": [{"id": "execute"}]}, context())
            self.store.add_task(run, "worker", self.repo, command, effects=["local_write"])
            with self.assertRaises(PermissionError):
                Coordinator(self.store).run(run, approved_local=True)
            self.assertEqual(self.store.tasks(run)[0]["attempts"], 0)
        with self.assertRaises(ValueError):
            self.store.add_task(run, "unknown", self.repo, python("pass"), effects=["invented_effect"])
        run = self.store.create_run("no-worker-publication", {"stages": [{"id": "execute"}]}, context())
        self.store.add_task(run, "publish", self.repo, ["gh", "pr", "create"], effects=["external_write"])
        with self.assertRaisesRegex(PermissionError, "reconciled delivery"):
            Coordinator(self.store).run(run, approved_local=True, approved_external=True)

    def test_reviewer_cannot_claim_success_without_structured_evidence(self):
        run = self.store.create_run("bad-review", quick_recipe(True), context(True))
        self.store.add_task(run, "work", self.repo, python("pass"))
        self.store.add_task(run, "check", self.repo, python("pass"), needs=["work"], kind="verify")
        self.store.add_task(run, "review", self.repo, python("print('looks good')"), needs=["check"], kind="review")
        self.assertEqual(Coordinator(self.store).run(run, approved_local=True)["state"], "failed")
        self.assertIn("review requires structured", self.store.tasks(run)[2]["result"]["error"])

    def test_verification_cannot_modify_files(self):
        run = self.store.create_run("modified-check", quick_recipe(), context())
        self.store.add_task(run, "work", self.repo, python("pass"))
        self.store.add_task(run, "check", self.repo, python("from pathlib import Path; Path('initial.txt').write_text('oops')"),
                            needs=["work"], kind="verify")
        self.assertEqual(Coordinator(self.store).run(run, approved_local=True)["state"], "failed")

    def test_bypass_and_provider_modes_rejected(self):
        for argv, provider in [(["codex", "exec", "--dangerously-bypass-approvals-and-sandbox"], "codex"),
                               (["claude", "-p", "--permission-mode=bypassPermissions"], "claude"),
                               (["codex", "exec", "--sandbox", "workspace-write", "--cd", "/tmp"], "codex"),
                               (["codex", "exec", "hello"], "codex"),
                               (["opencode", "run", "--auto"], "opencode")]:
            with self.subTest(argv=argv), self.assertRaises(ValueError):
                validate_argv(argv, provider)
        self.assertEqual(validate_argv(["codex", "exec", "--sandbox", "workspace-write", "fix"], "codex")[1], "exec")


if __name__ == "__main__":
    unittest.main()
