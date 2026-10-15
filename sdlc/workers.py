"""Bounded local subprocess workers in isolated git worktrees.

Worktrees prevent accidental shared-tree edits; they are not security sandboxes.
Only explicitly approved, trusted argv may execute. Provider policies remain native.
"""

from concurrent.futures import ThreadPoolExecutor
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import threading
import time
import uuid

from .workflows import TERMINAL

PROVIDERS = {"command", "codex", "claude", "opencode", "cursor"}
RISKY = {"package_install", "migration", "data_change", "infrastructure_change", "high_risk_change"}
BYPASS = {"--dangerously-bypass-approvals-and-sandbox", "--dangerously-skip-permissions",
          "--allow-dangerously-skip-permissions", "--dangerously-bypass-hook-trust",
          "--ignore-rules", "--force", "--yolo", "--auto", "--approve-for-me"}


def validate_argv(argv, provider="command"):
    if provider not in PROVIDERS:
        raise ValueError("unsupported provider")
    if not isinstance(argv, list) or not argv or any(not isinstance(x, str) or "\x00" in x for x in argv):
        raise ValueError("command must be a nonempty argv array")
    if any(x.split("=", 1)[0] in BYPASS or "bypassPermissions" in x or "danger-full-access" in x for x in argv):
        raise ValueError("permission/sandbox bypass is forbidden")
    if provider != "command":
        expected = "agent" if provider == "cursor" else provider
        if Path(argv[0]).name not in {expected, expected + ".exe", "cursor-agent" if provider == "cursor" else expected}:
            raise ValueError("provider argv executable mismatch")
        required = {"codex": "exec", "claude": "--print", "opencode": "run", "cursor": "--print"}[provider]
        if required not in argv and not (provider in {"claude", "cursor"} and "-p" in argv):
            raise ValueError(f"provider requires explicit noninteractive mode: {required}")
        # Prevent overriding worktree ownership or weakening the native sandbox through flags/config.
        forbidden = {"--cd", "-C", "--add-dir", "--directory", "--dir", "--config", "-c", "--settings",
                     "--permission-mode", "--profile", "--mcp-config", "--server", "--attach", "--remote-control"}
        if any(x.split("=", 1)[0] in forbidden for x in argv[1:]):
            raise ValueError("provider scope/policy overrides require a separate reviewed adapter")
        if provider == "codex":
            modes = []
            for pos, arg in enumerate(argv):
                if arg in {"--sandbox", "-s"} and pos + 1 < len(argv):
                    modes.append(argv[pos + 1])
                if arg.startswith("--sandbox="):
                    modes.append(arg.split("=", 1)[1])
            if modes != ["workspace-write"] and modes != ["read-only"]:
                raise ValueError("Codex worker requires one explicit read-only/workspace-write sandbox")
    return argv


def probe_provider(provider):
    executable = "agent" if provider == "cursor" else provider
    path = shutil.which(executable) or (shutil.which("cursor-agent") if provider == "cursor" else None)
    if not path:
        return {"provider": provider, "available": False, "reason": f"{executable} not installed"}
    try:
        version = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=10)
        help_args = [path] + (["exec", "--help"] if provider == "codex" else
                              ["run", "--help"] if provider == "opencode" else ["--help"])
        help_result = subprocess.run(help_args, capture_output=True, text=True, timeout=10)
        required = {"codex": "--sandbox", "claude": "--print", "opencode": "run", "cursor": "--print"}[provider]
        available = version.returncode == 0 and help_result.returncode == 0 and required in help_result.stdout
        return {"provider": provider, "available": available, "path": path,
                "version": version.stdout.strip()[:1000], "help_checked": required,
                "sandbox": "native workspace-write/read-only" if provider == "codex" else
                "native provider permissions; no OS filesystem/network confinement supplied by SDLCkit"}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"provider": provider, "available": False, "reason": str(exc)}


def process_identity(pid):
    try:
        # Linux /proc field 22 identifies a process despite PID reuse.
        data = Path(f"/proc/{pid}/stat").read_text()
        return data.rsplit(")", 1)[1].split()[19]
    except (OSError, IndexError):
        return None


def process_alive(pid, identity=None):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:
        if Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] == "Z":
            return False
    except (OSError, IndexError):
        pass
    current = process_identity(pid)
    return not identity or not current or current == identity


def terminate_group(pid):
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + 1
    while process_alive(pid) and time.monotonic() < deadline:
        time.sleep(0.02)
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def git(repo, *args):
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=60,
                            env=os.environ | {"GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1"})
    if result.returncode:
        raise RuntimeError(f"git {' '.join(args[:2])}: {result.stderr.strip()[:2000]}")
    return result.stdout.rstrip("\n")


def validate_snapshot(worktree, config, base="HEAD"):
    """Never turn generated edits or secret-bearing files into automatic snapshots."""
    from .policy import generated_path
    paths = set(git(worktree, "diff", "--name-only", "-z", base).split("\x00"))
    paths.update(git(worktree, "ls-files", "--others", "--exclude-standard", "-z").split("\x00"))
    for relative in paths - {""}:
        path = worktree / relative
        if not path.exists() and not path.is_symlink():
            continue
        name = path.name.lower()
        secret = (name == ".env" or name.startswith(".env.") and not name.endswith((".example", ".sample", ".template"))
                  or name in {".npmrc", ".pypirc", ".netrc", "credentials.json", "secrets.json", "token.json"}
                  or name.startswith(("id_rsa", "id_ed25519")) or name.endswith((".pem", ".key", ".p12", ".pfx")))
        if secret:
            raise PermissionError(f"snapshot refuses secret path: {relative}")
        if generated_path(relative, config):
            raise PermissionError(f"snapshot refuses generated path; regenerate/review separately: {relative}")
        if path.is_symlink():
            if not path.resolve().is_relative_to(worktree.resolve()):
                raise PermissionError(f"snapshot refuses escaping symlink: {relative}")
            continue
        if path.is_file() and path.stat().st_size <= 2097152:
            content = path.read_bytes()
            if re.search(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\b(?:ghp_|github_pat_|sk-proj-)[A-Za-z0-9_]{20,}", content):
                raise PermissionError(f"snapshot refuses secret-like content: {relative}")


@contextlib.contextmanager
def repo_lock(repo):
    import fcntl
    common = Path(git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    with (common / "sdlckit-coordinator.lock").open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def directory_bytes(root, limit):
    total = 0
    for base, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if d != ".git"]
        for name in files:
            try:
                path = Path(base) / name
                if not path.is_symlink():
                    total += path.stat().st_size
            except FileNotFoundError:
                pass
            if total > limit:
                return total
    return total


class Coordinator:
    def __init__(self, store, state_root=None, max_workers=1):
        if os.name != "posix":
            raise RuntimeError("worker process groups and repository locks require POSIX; use WSL on Windows")
        if not isinstance(max_workers, int) or not 1 <= max_workers <= 32:
            raise ValueError("max_workers must be 1..32")
        self.store = store
        self.root = Path(state_root or store.path.parent / "workers").resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.max_workers = max_workers
        self.owner = uuid.uuid4().hex
        self.stop_event = threading.Event()

    def stop(self):
        self.stop_event.set()

    def _authorize(self, tasks, approved_local, approved_external, approved_provider, approved_effects):
        from .config import load_for_target
        from .policy import require_effect, classify_command, EXTERNAL_EFFECTS
        if not approved_local:
            raise PermissionError("execution requires --approve-local for the exact stored command plan")
        for task in tasks:
            spec = task["spec"]
            config = load_for_target(spec["repo"])
            command_text = shlex.join(spec["argv"])
            if re.search(r"\b(?:gh\s+pr|glab\s+mr)\s+(?:create|edit|merge|close|review|comment)\b", command_text):
                raise PermissionError("remote publication requires the reconciled delivery adapter, not a worker command")
            run = self.store.run(task["run_id"])
            if run["context"].get("task", {}).get("high_risk") or run["recipe"].get("id") == "high-risk":
                require_effect("high_risk_change", config=config, approved="high_risk_change" in approved_effects,
                               scope=spec["repo"])
            validate_argv(spec["argv"], spec["provider"])
            if "external_write" in spec["effects"] and not approved_external:
                raise PermissionError("external command effects require --approve-external")
            for effect in set(spec["effects"]) | {classify_command(shlex.join(spec["argv"])), "worktree", "local_commit"}:
                approved = effect in approved_effects if effect in RISKY else (
                    approved_external if effect in EXTERNAL_EFFECTS else approved_local)
                require_effect(effect, config=config, approved=approved, scope=spec["repo"])
            self.store.event(task["run_id"], task["id"], "command.authorized",
                             {"declared_effects": spec["effects"], "observed_effect": classify_command(shlex.join(spec["argv"])),
                              "scope": spec["repo"], "approved_risky_effects": list(approved_effects)})
            if spec["provider"] != "command":
                if not approved_provider:
                    raise PermissionError("provider automation requires --approve-provider and reviewed native permissions")
                probe = probe_provider(spec["provider"])
                if not probe["available"]:
                    raise RuntimeError(f"provider capability unavailable: {probe}")

    def _allocate(self, run_id, task, attempt):
        spec = task["spec"]
        repo = spec["repo"]
        task_root = self.root / run_id / task["id"] / attempt
        task_root.mkdir(parents=True, mode=0o700)
        worktree = task_root / "tree"
        branch = f"sdlc/{run_id}/{task['id']}/{attempt[:12]}"
        dependencies = [t for t in self.store.tasks(run_id) if t["id"] in
                        {n.rstrip("?") for n in spec["needs"]} and t["state"] == "succeeded"]
        related = [t for t in dependencies if t["spec"]["repo"] == repo and t["result"].get("revision")]
        base = related[0]["result"]["revision"] if related else spec["input_revision"]
        with repo_lock(repo):
            git(repo, "worktree", "add", "-b", branch, str(worktree), base)
        for dependency in related[1:]:
            git(worktree, "-c", "user.name=SDLCkit", "-c", "user.email=sdlckit@localhost",
                "merge", "--no-edit", dependency["result"]["revision"])
        return task_root, worktree, branch, base, dependencies

    def _worker(self, run_id, task, attempt):
        spec = task["spec"]
        evidence = {"argv": spec["argv"], "provider": spec["provider"], "declared_effects": spec["effects"],
                    "exit_code": None, "attempt": attempt, "started": time.time()}
        process = None
        try:
            task_root, worktree, branch, base, dependencies = self._allocate(run_id, task, attempt)
            evidence.update(worktree=str(worktree), branch=branch, input_revision=base)
            self.store.event(run_id, task["id"], "worker.isolated", evidence)
            baseline = directory_bytes(worktree, spec["max_disk_bytes"])
            start_revision = git(worktree, "rev-parse", "HEAD")
            log_path = task_root / "output.log"
            result_path = task_root / "result.json"
            evidence.update(log=str(log_path), structured_result=str(result_path))
            env = os.environ | {"SDLC_RUN_ID": run_id, "SDLC_TASK_ID": task["id"],
                                "SDLC_RESULT_PATH": str(result_path), "SDLC_WORKTREE": str(worktree),
                                "SDLC_DEPENDENCIES": json.dumps({t["id"]: t["result"] for t in dependencies}),
                                "SDLC_WORK_ITEM": json.dumps(self.store.run(run_id)["context"].get("work_item", {})),
                                "GIT_TERMINAL_PROMPT": "0"}
            # Pipes are drained in a bounded reader, so output cannot fill RAM or the disk.
            process = subprocess.Popen(spec["argv"], cwd=worktree, env=env, stdin=subprocess.DEVNULL,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
            self.store.heartbeat(run_id, task["id"], self.owner, process.pid, process_identity(process.pid))
            bytes_written = [0]
            overflow = threading.Event()

            def drain():
                with log_path.open("wb") as log:
                    while True:
                        chunk = os.read(process.stdout.fileno(), 65536)
                        if not chunk:
                            break
                        remaining = max(0, spec["max_log_bytes"] - bytes_written[0])
                        log.write(chunk[:remaining])
                        bytes_written[0] += min(len(chunk), remaining)
                        if len(chunk) > remaining:
                            overflow.set()

            reader = threading.Thread(target=drain, daemon=True)
            reader.start()
            start = time.monotonic()
            last_heartbeat = start
            while process.poll() is None:
                reason = None
                if self.stop_event.is_set() or self.store.run(run_id)["cancelled"]:
                    reason = "cancelled"
                elif time.monotonic() - start > spec["timeout"]:
                    reason = "timeout budget exceeded"
                elif overflow.is_set():
                    reason = "log budget exceeded"
                elif directory_bytes(worktree, baseline + spec["max_disk_bytes"]) > baseline + spec["max_disk_bytes"]:
                    reason = "disk budget exceeded"
                if reason:
                    evidence["error"] = reason
                    terminate_group(process.pid)
                    break
                if time.monotonic() - last_heartbeat > 5:
                    if not self.store.heartbeat(run_id, task["id"], self.owner):
                        evidence["error"] = "lost durable ownership"
                        terminate_group(process.pid)
                        break
                    last_heartbeat = time.monotonic()
                time.sleep(0.05)
            evidence["exit_code"] = process.wait(timeout=5)
            # Kill grandchildren left after the leader exits, including inherited output pipes.
            terminate_group(process.pid)
            reader.join(timeout=2)
            if reader.is_alive():
                terminate_group(process.pid)
                reader.join(timeout=2)
            process.stdout.close()
            if overflow.is_set():
                evidence["error"] = "log budget exceeded"
            if directory_bytes(worktree, baseline + spec["max_disk_bytes"]) > baseline + spec["max_disk_bytes"]:
                evidence["error"] = "disk budget exceeded"
            evidence["log_sha256"] = hashlib.sha256(log_path.read_bytes()).hexdigest()
            evidence["log_bytes"] = bytes_written[0]
            if result_path.exists():
                if result_path.is_symlink() or result_path.stat().st_size > spec["max_log_bytes"]:
                    raise ValueError("invalid structured result size/path")
                result = json.loads(result_path.read_text())
                if not isinstance(result, dict):
                    raise ValueError("structured result must be an object")
                evidence["result"] = result
            if spec["kind"] == "review" and not evidence.get("error") and evidence["exit_code"] == 0:
                result = evidence.get("result", {})
                if result.get("passed") is not True or not isinstance(result.get("findings"), list):
                    raise ValueError("review requires structured {passed:true,findings:[]} result")
                findings = result["findings"]
                if any(not isinstance(f, dict) or f.get("severity") not in
                       {"blocker", "critical", "high", "medium", "low", "info"} for f in findings):
                    raise ValueError("invalid review finding severity")
                if any(f["severity"] in {"blocker", "critical", "high"} for f in findings):
                    raise ValueError("review contains blocking findings")
            changed = git(worktree, "status", "--porcelain")
            if (changed or git(worktree, "rev-parse", "HEAD") != start_revision) and spec["kind"] in {
                    "verify", "review", "context", "intake", "design", "report"}:
                raise ValueError("read/verification/review worker changed repository files")
            if evidence["exit_code"] == 0 and not evidence.get("error"):
                from .config import load_for_target
                validate_snapshot(worktree, load_for_target(spec["repo"]), start_revision)
                if changed:
                    git(worktree, "add", "--all")
                    # Internal checkpoint, not a delivery commit: no hook execution or hook overrides.
                    # The requested delivery adapter must apply the target's commit/review hooks.
                    validate_snapshot(worktree, load_for_target(spec["repo"]), start_revision)
                    parent = git(worktree, "rev-parse", "HEAD")
                    tree = git(worktree, "write-tree")
                    revision = git(worktree, "-c", "user.name=SDLCkit", "-c", "user.email=sdlckit@localhost",
                                   "commit-tree", tree, "-p", parent, "-m", f"SDLCkit checkpoint {run_id}/{task['id']}")
                    git(worktree, "update-ref", f"refs/heads/{branch}", revision, parent)
                    if git(worktree, "status", "--porcelain"):
                        raise ValueError("checkpoint left uncommitted changes; snapshot requires review")
                evidence["revision"] = git(worktree, "rev-parse", "HEAD")
            state = "succeeded" if evidence["exit_code"] == 0 and not evidence.get("error") else "failed"
            if evidence.get("error") == "cancelled":
                state = "cancelled"
        except Exception as exc:
            evidence["error"] = str(exc)
            state = "failed"
            if process and process.poll() is None:
                terminate_group(process.pid)
                evidence["exit_code"] = process.wait(timeout=5)
        evidence["finished"] = time.time()
        self.store.finish(run_id, task["id"], self.owner, attempt, state, evidence)
        return state

    def run(self, run_id, approved_local=False, approved_external=False, approved_provider=False,
            launch_guard=None, approved_effects=()):
        tasks = self.store.validate_tasks(run_id)
        self._authorize(tasks, approved_local, approved_external, approved_provider, approved_effects)
        if self.store.run(run_id)["state"] in {"verified", "delivered"}:
            self.store.assert_deliverable(run_id)
            return self.store.run(run_id)
        resource = f"run:{run_id}"
        if not self.store.acquire_lease(resource, self.owner):
            raise RuntimeError("run is owned by another coordinator")
        futures = {}
        self.store.event(run_id, None, "execution.approved", {"local": approved_local, "external": approved_external,
                                                            "provider": approved_provider, "max_workers": self.max_workers})
        try:
            self.store.recover(run_id)
            if any(t["state"] == "running" for t in self.store.tasks(run_id)):
                raise RuntimeError("run has live or unexpired orphan workers; recover/stop first")
            self.store.set_run_state(run_id, "running")
            with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
                while True:
                    if not self.store.acquire_lease(resource, self.owner):
                        self.stop()
                    tasks = self.store.refresh(run_id)
                    for future in list(futures):
                        if future.done():
                            future.result()
                            del futures[future]
                    if not self.stop_event.is_set() and not self.store.run(run_id)["cancelled"]:
                        for task in tasks:
                            if len(futures) >= self.max_workers:
                                break
                            if task["state"] != "ready":
                                continue
                            if launch_guard is not None and not launch_guard():
                                continue
                            attempt = self.store.claim(run_id, task["id"], self.owner)
                            if attempt:
                                futures[pool.submit(self._worker, run_id, task, attempt)] = task["id"]
                    if not futures:
                        tasks = self.store.refresh(run_id)
                        if self.stop_event.is_set() or (launch_guard is not None and not launch_guard()):
                            self.store.set_run_state(run_id, "blocked")
                            break
                        if all(t["state"] in TERMINAL for t in tasks):
                            if self.store.run(run_id)["cancelled"]:
                                self.store.set_run_state(run_id, "cancelled")
                            elif any(t["state"] == "failed" for t in tasks):
                                self.store.set_run_state(run_id, "failed")
                            elif any(t["state"] == "blocked" for t in tasks):
                                self.store.set_run_state(run_id, "blocked")
                            else:
                                try:
                                    self.store.assert_deliverable(run_id)
                                    self.store.set_run_state(run_id, "verified")
                                except ValueError as exc:
                                    self.store.event(run_id, None, "delivery.blocked", {"reason": str(exc)})
                                    self.store.set_run_state(run_id, "blocked")
                            break
                    time.sleep(0.05)
            return self.store.run(run_id)
        finally:
            self.store.release_lease(resource, self.owner)

    def stop_orphans(self, run_id):
        self.store.cancel(run_id)
        for task in self.store.tasks(run_id):
            if task["state"] == "running" and task["pid"]:
                # Require the captured process identity; do not signal an unrelated reused PID.
                if task["process_identity"] and process_identity(task["pid"]) == task["process_identity"]:
                    terminate_group(task["pid"])
                    self.store.event(run_id, task["id"], "worker.stop_signal", {"pid": task["pid"]})
