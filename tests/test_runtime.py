import json
import contextlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from sdlc.runtime import Store
from sdlc.runtime_cli import main
from sdlc.workers import Coordinator


def repository(path):
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "test@example.invalid"], check=True)
    (path / "initial.txt").write_text("initial\n")
    subprocess.run(["git", "-C", str(path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-qm", "initial"], check=True)
    return path


def python(code):
    return [sys.executable, "-c", code]


def quick_recipe(review=False):
    stages = [{"id": "execute"}, {"id": "verify", "needs": ["execute"]}]
    if review:
        stages.append({"id": "review", "needs": ["verify"]})
    stages.append({"id": "deliver", "needs": ["review" if review else "verify"]})
    return {"id": "test", "stages": stages}


def context(review=False):
    return {"task": {"complexity": "trivial", "cross_repo": False, "investigation": False,
                     "high_risk": False}, "policy": {"requires_review": review}}


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="sdlc runtime ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = repository(self.root / "project")
        self.store = Store(self.root / "state" / "runs.db")

    def test_real_verification_review_and_persisted_resume(self):
        run = self.store.create_run("work-1", quick_recipe(True), context(True))
        self.store.add_task(run, "implement", self.repo, python("from pathlib import Path; Path('feature').write_text('ok')"))
        self.store.add_task(run, "tests", self.repo, python("from pathlib import Path; assert Path('feature').read_text() == 'ok'"),
                            needs=["implement"], kind="verify")
        self.store.add_task(run, "reviewer", self.repo,
                            python("import os,json; from pathlib import Path; assert Path('feature').read_text() == 'ok'; "
                                   "Path(os.environ['SDLC_RESULT_PATH']).write_text(json.dumps({'passed':True,'findings':[]}))"),
                            needs=["tests"], kind="review")
        result = Coordinator(self.store).run(run, approved_local=True)
        self.assertEqual(result["state"], "verified")
        self.assertFalse((self.repo / "feature").exists())
        reopened = Store(self.store.path)
        self.assertTrue(reopened.assert_deliverable(run))
        self.assertTrue(all(t["result"]["exit_code"] == 0 for t in reopened.tasks(run)))
        attempts = [t["attempts"] for t in reopened.tasks(run)]
        Coordinator(reopened).run(run, approved_local=True)
        self.assertEqual([t["attempts"] for t in reopened.tasks(run)], attempts)
        events = reopened.history(run)
        self.assertTrue(any(e["type"] == "worker.isolated" for e in events))

    def test_failed_check_remains_failed_and_blocks_delivery(self):
        run = self.store.create_run("work-2", quick_recipe(), context())
        self.store.add_task(run, "implement", self.repo, python("print('implemented')"))
        self.store.add_task(run, "tests", self.repo, python("raise SystemExit(7)"), needs=["implement"], kind="verify")
        result = Coordinator(self.store).run(run, approved_local=True)
        self.assertEqual(result["state"], "failed")
        self.assertEqual(self.store.tasks(run)[1]["result"]["exit_code"], 7)
        with self.assertRaises(ValueError):
            self.store.assert_deliverable(run)

    def test_dependency_retry_after_failed_worker(self):
        marker = self.root / "attempted"
        run = self.store.create_run("work-retry", quick_recipe(), context())
        code = f"from pathlib import Path; p=Path({str(marker)!r}); old=p.exists(); p.touch(); raise SystemExit(0 if old else 2)"
        self.store.add_task(run, "implement", self.repo, python(code), max_attempts=2)
        self.store.add_task(run, "tests", self.repo, python("print('checks')"), needs=["implement"], kind="verify")
        self.assertEqual(Coordinator(self.store).run(run, approved_local=True)["state"], "failed")
        self.assertEqual(self.store.tasks(run)[1]["state"], "blocked")
        self.store.retry(run, "implement")
        self.assertEqual(Coordinator(self.store).run(run, approved_local=True)["state"], "verified")
        self.assertEqual(self.store.tasks(run)[0]["attempts"], 2)
        with self.assertRaises(ValueError):
            self.store.retry(run, "implement")

    def test_skip_is_not_verification_success(self):
        recipe = quick_recipe()
        recipe["stages"][1]["when"] = False
        recipe["stages"][2]["needs"] = ["verify?"]
        run = self.store.create_run("work-skip", recipe, context())
        self.store.add_task(run, "implement", self.repo, python("print('done')"))
        self.store.add_task(run, "checks", self.repo, python("raise SystemExit(99)"), needs=["implement"], kind="verify")
        self.assertEqual(Coordinator(self.store).run(run, approved_local=True)["state"], "blocked")
        self.assertEqual(self.store.tasks(run)[1]["state"], "skipped")
        with self.assertRaises(ValueError):
            self.store.assert_deliverable(run)

    def test_crash_recovery_and_expired_lease(self):
        run = self.store.create_run("work-crash", quick_recipe(), context())
        self.store.add_task(run, "implement", self.repo, python("print('retry')"), max_attempts=2)
        self.store.add_task(run, "checks", self.repo, python("print('pass')"), needs=["implement"], kind="verify")
        self.store.refresh(run)
        attempt = self.store.claim(run, "implement", "dead-owner")
        self.assertIsNotNone(attempt)
        self.assertEqual(self.store.recover(run), [])
        with self.store.connect() as db:
            db.execute("UPDATE tasks SET lease=? WHERE run_id=? AND id='implement'", (time.time() - 1, run))
        self.assertEqual(Store(self.store.path).recover(run), ["implement"])
        self.assertEqual(self.store.tasks(run)[0]["state"], "failed")
        self.store.retry(run, "implement")
        self.assertEqual(Coordinator(self.store).run(run, approved_local=True)["state"], "verified")

    def test_missing_stage_dependency_and_authorization(self):
        run = self.store.create_run("work-missing", quick_recipe(), context())
        self.store.add_task(run, "implement", self.repo, python("pass"))
        with self.assertRaises(ValueError):
            Coordinator(self.store).run(run, approved_local=True)
        self.store.add_task(run, "checks", self.repo, python("pass"), kind="verify", needs=["implement"])
        with self.assertRaises(PermissionError):
            Coordinator(self.store).run(run)
        self.assertTrue(all(t["attempts"] == 0 for t in self.store.tasks(run)))

    def test_run_and_repo_leases(self):
        self.assertTrue(self.store.acquire_lease("repo:test", "one"))
        self.assertFalse(self.store.acquire_lease("repo:test", "two"))
        self.store.release_lease("repo:test", "two")
        self.assertFalse(self.store.acquire_lease("repo:test", "two"))
        self.store.release_lease("repo:test", "one")
        self.assertTrue(self.store.acquire_lease("repo:test", "two"))

    def test_multi_repository_output_needs_aggregate_integration_and_review(self):
        other = repository(self.root / "other")
        run = self.store.create_run("integration-missing", quick_recipe(), context())
        self.store.add_task(run, "one", self.repo, python("pass"))
        self.store.add_task(run, "two", other, python("pass"))
        self.store.add_task(run, "checks", self.repo, python("pass"), kind="verify", needs=["one", "two"])
        self.assertEqual(Coordinator(self.store, max_workers=2).run(run, approved_local=True)["state"], "blocked")
        with self.assertRaisesRegex(ValueError, "aggregate integration"):
            self.store.assert_deliverable(run)

    def test_delivery_rejects_post_verification_edits_and_log_tampering(self):
        run = self.store.create_run("tampering", quick_recipe(), context())
        self.store.add_task(run, "work", self.repo, python("print('work')"))
        self.store.add_task(run, "checks", self.repo, python("print('check')"), needs=["work"], kind="verify")
        self.assertEqual(Coordinator(self.store).run(run, approved_local=True)["state"], "verified")
        task = self.store.tasks(run)[0]
        path = Path(task["result"]["worktree"]) / "initial.txt"
        path.write_text("unverified edit")
        with self.assertRaisesRegex(ValueError, "changed after recorded"):
            self.store.assert_deliverable(run)
        path.write_text("initial\n")
        Path(task["result"]["log"]).write_text("forged output")
        with self.assertRaisesRegex(ValueError, "log changed"):
            self.store.assert_deliverable(run)

    def test_high_risk_needs_separate_approval(self):
        for by_context in [False, True]:
            with self.subTest(context=by_context):
                recipe = quick_recipe()
                risk_context = context()
                if by_context:
                    risk_context["task"]["high_risk"] = True
                else:
                    recipe["id"] = "high-risk"
                run = self.store.create_run("risk", recipe, risk_context)
                self.store.add_task(run, "work", self.repo, python("pass"))
                self.store.add_task(run, "checks", self.repo, python("pass"), needs=["work"], kind="verify")
                with self.assertRaises(PermissionError):
                    Coordinator(self.store).run(run, approved_local=True, approved_external=True)
                self.assertEqual(self.store.tasks(run)[0]["attempts"], 0)
                self.assertEqual(Coordinator(self.store).run(run, approved_local=True,
                                 approved_effects=["high_risk_change"])["state"], "verified")

    def test_documented_cli_plan_create_execute_status_history(self):
        plan = {"work_id": "cli-smoke", "run_id": "cli-smoke-run", "recipe": quick_recipe(), "context": context(),
                "tasks": [{"id": "implementation", "repo": str(self.repo), "argv": python(
                    "from pathlib import Path; Path('example.txt').write_text('ready\\n')")},
                    {"id": "checks", "repo": str(self.repo), "argv": python(
                    "from pathlib import Path; assert Path('example.txt').read_text() == 'ready\\n'"),
                     "kind": "verify", "needs": ["implementation"]}]}
        plan_path = self.root / "run.json"
        plan_path.write_text(json.dumps(plan))
        prefix = ["--db", str(self.store.path)]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(prefix + ["create", "--plan", str(plan_path)]), 0)
            self.assertEqual(main(prefix + ["execute", "cli-smoke-run"]), 1)
            self.assertEqual(main(prefix + ["execute", "cli-smoke-run", "--approve-local"]), 0)
            self.assertEqual(main(prefix + ["status", "cli-smoke-run"]), 0)
            self.assertEqual(main(prefix + ["history", "cli-smoke-run"]), 0)
            self.assertEqual(main(prefix + ["delivery-gate", "cli-smoke-run"]), 0)
        self.assertFalse((self.repo / "example.txt").exists())


if __name__ == "__main__":
    unittest.main()
