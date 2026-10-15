"""Cross-module acceptance tests using real CLI processes and disposable projects."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from sdlc.config import load_workflow
from sdlc.delivery import prepare, publish
from sdlc.installer import uninstall
from sdlc.runtime import Store
from sdlc.workers import Coordinator

ROOT = Path(__file__).resolve().parents[1]


class EndToEndTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null"})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.temp = tempfile.TemporaryDirectory(prefix="sdlc acceptance ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def git(self, repo, *args):
        result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=True)
        return result.stdout.decode().strip()

    def project(self, name, files):
        repo = self.root / name
        repo.mkdir()
        self.git(repo, "init", "-b", "trunk")
        self.git(repo, "config", "user.name", "Acceptance Test")
        self.git(repo, "config", "user.email", "test@example.invalid")
        for name, text in files.items():
            path = repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        self.git(repo, "add", ".")
        self.git(repo, "commit", "-m", "initial")
        return repo

    def cli(self, *args, expected=0):
        result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/sdlc.py"), *map(str, args)],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, expected, result.stderr or result.stdout)
        return json.loads(result.stdout)

    def test_external_workspace_mixed_stacks_dry_run_idempotency_and_preservation(self):
        self.project("go-api", {"go.mod": "module example.invalid/api\n\ngo 1.22\n", "main.go": "package main\nfunc main() {}\n"})
        python = self.project("python-api", {"pyproject.toml": "[project]\nname = 'example'\nversion = '0.1'\n", "AGENTS.md": "Use unittest. Preserve these rules.\n", "tests/test_app.py": "import unittest\n"})
        self.project("ui", {"package.json": '{"scripts":{"test":"node --test","lint":"eslint ."}}', "tsconfig.json": "{}"})
        before = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        dry = self.cli("setup", "--target", self.root, "--harness", "all", "--dry-run", "--merge")
        self.assertEqual(dry["status"], "preview")
        after = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        first = self.cli("setup", "--target", self.root, "--harness", "all", "--merge", "--non-interactive")
        self.assertEqual(first["status"], "installed")
        second = self.cli("setup", "--target", self.root, "--harness", "all", "--merge", "--non-interactive")
        self.assertEqual(second["operation_count"], 0)
        instructions = (python / "AGENTS.md").read_text()
        self.assertTrue(instructions.startswith("Use unittest. Preserve these rules.\n"))
        self.assertNotIn("task lint", (python / ".sdlc/instructions.md").read_text())
        self.assertEqual(len(first["inventory"]["projects"]), 3)
        for project in first["inventory"]["projects"]:
            self.assertTrue((Path(project["path"]) / ".codex/config.toml").exists())
            self.assertTrue((Path(project["path"]) / ".cursor/rules/sdlc-core.mdc").exists())
        self.assertEqual(uninstall(self.root)["status"], "uninstalled")
        self.assertEqual((python / "AGENTS.md").read_text(), "Use unittest. Preserve these rules.\n")

    def test_prompt_to_real_worker_verification_and_committed_patch(self):
        repo = self.project("python", {"app.py": "def value():\n    return 1\n",
                                      "tests/test_app.py": "import unittest\nfrom app import value\nclass TestValue(unittest.TestCase):\n    def test_value(self):\n        self.assertEqual(value(), 2)\n"})
        item = self.cli("intake", "Change value() to return 2", "--source", "prompt", "--root", repo,
                        "--criterion", "value() returns 2", "--delivery", "patch")
        self.assertEqual(item["requested_delivery"], "patch")
        recipe = load_workflow("quick-fix")
        store = Store(self.root / "state/runtime.sqlite3")
        run_id = store.create_run(item["work_id"], recipe, {"task": {"complexity": "trivial"},
                                                          "policy": {"requires_review": False}, "work_item": item})
        store.add_task(run_id, "intake", repo, [sys.executable, "-c", "pass"], kind="intake", effects=["read"])
        store.add_task(run_id, "context", repo, [sys.executable, "-c", "pass"], needs=["intake"], kind="context", effects=["read"])
        store.add_task(run_id, "execute", repo, [sys.executable, "-c", "from pathlib import Path; Path('app.py').write_text('def value():\\n    return 2\\n')"], needs=["context"],
                       acceptance_criteria=["AC-1"], expected_paths=["app.py"])
        store.add_task(run_id, "verify", repo, [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests"],
                       needs=["execute"], kind="verify", effects=["read"])
        baseline = self.git(repo, "rev-parse", "HEAD")
        result = Coordinator(store).run(run_id, approved_local=True)
        self.assertEqual(result["state"], "verified")
        check = next(task for task in store.tasks(run_id) if task["id"] == "verify")
        change = next(task for task in store.tasks(run_id) if task["id"] == "execute")
        self.assertEqual(change["spec"]["acceptance_criteria"], ["AC-1"])
        self.assertEqual(change["spec"]["expected_paths"], ["app.py"])
        prepared = prepare(check["result"]["worktree"], "patch", item["work_id"], since=baseline)
        patch_result = publish(prepared, output="result.patch", approved_local=True,
                               runtime_db=store.path, run_id=run_id)
        self.assertIn("+    return 2", Path(patch_result["path"]).read_text())
        self.assertEqual((repo / "app.py").read_text(), "def value():\n    return 1\n")
        self.assertEqual(check["result"]["exit_code"], 0)
        self.assertTrue(store.assert_deliverable(run_id))
        self.assertEqual(store.run(run_id)['state'], 'delivered')
        repeated = publish(prepared, output='result.patch', approved_local=True, runtime_db=store.path, run_id=run_id)
        self.assertEqual(repeated, patch_result)

    def test_target_policy_blocks_external_delivery_even_with_flag(self):
        repo = self.project("policy", {"README.md": "project\n"})
        self.git(repo, "switch", "-c", "work/test")
        profile = repo / ".sdlc/project.json"
        profile.parent.mkdir()
        profile.write_text(json.dumps({"schema_version": 2, "project": {"id": "policy", "policy": {"external_write": "forbidden"}}}))
        self.git(repo, "add", ".sdlc/project.json")
        self.git(repo, "commit", "-m", "project policy")
        result = subprocess.run([sys.executable, "-B", str(ROOT / "scripts/deliver.py"), "github_pr", "--repo", str(repo),
                                 "--work-id", "work-denied", "--base", "trunk", "--approve-external"],
                                capture_output=True, text=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("forbidden", result.stderr)


if __name__ == "__main__":
    unittest.main()
