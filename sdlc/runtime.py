"""SQLite-backed local task journal. Opening the store never launches workers."""

import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import time
import uuid

from .workflows import condition, readiness, validate_recipe


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,119}", value):
        raise ValueError("invalid identifier")
    return value


class Store:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, work_id TEXT NOT NULL, state TEXT NOT NULL,
                    recipe TEXT NOT NULL, context TEXT NOT NULL, created REAL NOT NULL,
                    updated REAL NOT NULL, cancelled INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS tasks (
                    run_id TEXT NOT NULL REFERENCES runs(id), id TEXT NOT NULL,
                    state TEXT NOT NULL, spec TEXT NOT NULL, result TEXT,
                    attempts INTEGER NOT NULL DEFAULT 0, max_attempts INTEGER NOT NULL,
                    owner TEXT, lease REAL, pid INTEGER, process_identity TEXT,
                    PRIMARY KEY(run_id,id));
                CREATE TABLE IF NOT EXISTS events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT,
                    task_id TEXT, time REAL NOT NULL, type TEXT NOT NULL, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS attempts (
                    id TEXT PRIMARY KEY, run_id TEXT NOT NULL, task_id TEXT NOT NULL,
                    number INTEGER NOT NULL, started REAL NOT NULL, finished REAL,
                    state TEXT NOT NULL, evidence TEXT);
                CREATE TABLE IF NOT EXISTS leases (
                    resource TEXT PRIMARY KEY, owner TEXT NOT NULL, expires REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS watches (
                    id TEXT PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 0,
                    config TEXT NOT NULL, updated REAL NOT NULL, last_poll REAL);
                CREATE TABLE IF NOT EXISTS queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, watch_id TEXT NOT NULL,
                    dedup TEXT NOT NULL, payload TEXT NOT NULL, state TEXT NOT NULL,
                    created REAL NOT NULL, run_id TEXT,
                    UNIQUE(watch_id,dedup));
                CREATE TABLE IF NOT EXISTS webhook_receipts (
                    watch_id TEXT NOT NULL, nonce TEXT NOT NULL, time REAL NOT NULL,
                    PRIMARY KEY(watch_id,nonce));
            """)
        os.chmod(self.path, 0o600)

    @contextlib.contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def _event(self, db, run_id, task_id, kind, data):
        db.execute("INSERT INTO events(run_id,task_id,time,type,data) VALUES(?,?,?,?,?)",
                   (run_id, task_id, time.time(), kind, json.dumps(data, sort_keys=True)))

    def event(self, run_id, task_id, kind, data):
        with self.connect() as db:
            self._event(db, run_id, task_id, kind, data)

    def create_run(self, work_id, recipe, context=None, run_id=None):
        validate_recipe(recipe)
        run_id = identifier(run_id or f"run-{uuid.uuid4().hex[:16]}")
        context = context or {"task": {"complexity": "standard", "cross_repo": False,
                                     "investigation": False, "high_risk": False}, "policy": {"requires_review": True}}
        # Resolve all conditions up front so incomplete context cannot half-start a run.
        for stage in recipe["stages"]:
            condition(stage.get("when"), context)
        with self.connect() as db:
            now = time.time()
            db.execute("INSERT INTO runs VALUES(?,?,?,?,?,?,?,0)",
                       (run_id, work_id, "pending", json.dumps(recipe), json.dumps(context), now, now))
            self._event(db, run_id, None, "run.created", {"work_id": work_id})
        return run_id

    def add_task(self, run_id, task_id, repo, argv, needs=None, kind="execute", effects=None,
                 max_attempts=1, timeout=600, provider="command", stage=None, when=None,
                 max_log_bytes=1048576, max_disk_bytes=268435456, integration=False,
                 acceptance_criteria=None, expected_paths=None):
        from .workers import validate_argv
        from .workers import git
        from .policy import LOCAL_EFFECTS, EXTERNAL_EFFECTS, APPROVAL_EFFECTS
        identifier(task_id)
        if kind not in {"intake", "context", "design", "execute", "verify", "review", "deliver", "report"}:
            raise ValueError("unsupported task kind")
        if kind == "deliver":
            raise ValueError("delivery uses a guarded delivery adapter, not a worker command")
        validate_argv(argv, provider)
        if not 1 <= max_attempts <= 10 or not 0 < timeout <= 86400:
            raise ValueError("invalid attempt/time budget")
        if not 1024 <= max_log_bytes <= 67108864 or not 4096 <= max_disk_bytes <= 10737418240:
            raise ValueError("invalid disk/log budget")
        if not Path(repo).is_dir():
            raise ValueError("repository does not exist")
        needs = needs or []
        if not isinstance(needs, list) or any(not isinstance(x, str) for x in needs):
            raise ValueError("invalid dependencies")
        run = self.run(run_id)
        stage = stage or kind
        stage_ids = {s["id"] for s in run["recipe"]["stages"]}
        if stage not in stage_ids:
            raise ValueError("task stage missing from recipe")
        effects = effects or ["local_write"]
        if not isinstance(effects, list) or not effects or not set(effects) <= LOCAL_EFFECTS | EXTERNAL_EFFECTS | APPROVAL_EFFECTS:
            raise ValueError("invalid declared command effects")
        if not isinstance(integration, bool) or integration and kind != "verify":
            raise ValueError("integration gate must be a verification task")
        for name, values in (("acceptance_criteria", acceptance_criteria), ("expected_paths", expected_paths)):
            if values is not None and (not isinstance(values, list) or any(not isinstance(x, str) or not x for x in values)):
                raise ValueError(f"{name} must be a list of nonempty strings")
        if expected_paths and any(Path(value).is_absolute() or ".." in Path(value).parts for value in expected_paths):
            raise ValueError("expected paths must be relative to the task repository")
        spec = dict(repo=str(Path(repo).resolve()), argv=argv, needs=needs, kind=kind, stage=stage,
                    effects=effects, timeout=timeout, provider=provider, when=when,
                    max_log_bytes=max_log_bytes, max_disk_bytes=max_disk_bytes, integration=integration,
                    acceptance_criteria=acceptance_criteria or [], expected_paths=expected_paths or [])
        spec["input_revision"] = git(repo, "rev-parse", "HEAD")
        condition(when, run["context"])
        with self.connect() as db:
            if db.execute("SELECT state FROM runs WHERE id=?", (run_id,)).fetchone()[0] != "pending":
                raise ValueError("cannot add tasks after run starts")
            db.execute("INSERT INTO tasks(run_id,id,state,spec,max_attempts) VALUES(?,?,?,?,?)",
                       (run_id, task_id, "pending", json.dumps(spec), max_attempts))
            self._event(db, run_id, task_id, "task.created", spec)

    def run(self, run_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise ValueError("unknown run")
        result = dict(row)
        result["recipe"] = json.loads(result["recipe"])
        result["context"] = json.loads(result["context"])
        return result

    def tasks(self, run_id):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM tasks WHERE run_id=? ORDER BY rowid", (run_id,)).fetchall()
        result = []
        for row in rows:
            task = dict(row)
            task["spec"] = json.loads(task["spec"])
            task["result"] = json.loads(task["result"]) if task["result"] else None
            result.append(task)
        return result

    def history(self, run_id=None):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM events WHERE (? IS NULL OR run_id=?) ORDER BY sequence",
                              (run_id, run_id)).fetchall()
        return [dict(row) | {"data": json.loads(row["data"])} for row in rows]

    def validate_tasks(self, run_id):
        tasks = self.tasks(run_id)
        if not tasks:
            raise ValueError("run has no tasks")
        validate_recipe({"stages": [{"id": t["id"], "needs": t["spec"]["needs"]} for t in tasks]})
        run = self.run(run_id)
        by_stage = {}
        for task in tasks:
            by_stage.setdefault(task["spec"]["stage"], []).append(task["id"])
        # Every selected stage must have an executable task except delivery, handled by its adapter.
        for stage in run["recipe"]["stages"]:
            if stage["id"] == "deliver":
                continue
            if condition(stage.get("when"), run["context"]) and stage["id"] not in by_stage:
                raise ValueError(f"selected stage has no task: {stage['id']}")
            for task in tasks:
                if task["spec"]["stage"] != stage["id"]:
                    continue
                needed = {n.rstrip("?") for n in task["spec"]["needs"]}
                for dep in stage.get("needs", []):
                    required = by_stage.get(dep.rstrip("?"), [])
                    if not dep.endswith("?") and not required:
                        raise ValueError(f"missing required stage dependency: {dep}")
                    if not set(required) <= needed:
                        raise ValueError("task DAG omits recipe stage dependencies")
        return tasks

    def set_run_state(self, run_id, state):
        if state not in {"pending", "running", "blocked", "failed", "cancelled", "verified", "delivered"}:
            raise ValueError("invalid run state")
        if state == "delivered":
            self.assert_deliverable(run_id)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute("SELECT state FROM runs WHERE id=?", (run_id,)).fetchone()
            if previous is None:
                raise ValueError("unknown run")
            transitions = {"pending": {"running", "blocked", "cancelled"},
                           "running": {"verified", "failed", "blocked", "cancelled"},
                           "blocked": {"pending", "running", "cancelled"},
                           "failed": {"pending", "running", "cancelled"},
                           "cancelled": {"pending"}, "verified": {"delivered"}, "delivered": set()}
            if state != previous[0] and state not in transitions[previous[0]]:
                raise ValueError(f"invalid run transition: {previous[0]} -> {state}")
            db.execute("UPDATE runs SET state=?,updated=? WHERE id=?", (state, time.time(), run_id))
            if state in {"verified", "delivered", "failed", "cancelled", "blocked"}:
                queue_state = "completed" if state in {"verified", "delivered"} else "failed"
                db.execute("UPDATE queue SET state=? WHERE run_id=?", (queue_state, run_id))
            self._event(db, run_id, None, "run.state", {"state": state})

    def refresh(self, run_id):
        run = self.run(run_id)
        tasks = self.tasks(run_id)
        statuses = {t["id"]: t["state"] for t in tasks}
        stages = {s["id"]: s for s in run["recipe"]["stages"]}
        with self.connect() as db:
            for task in tasks:
                if task["state"] not in {"pending", "ready"}:
                    continue
                spec = task["spec"]
                if run["cancelled"]:
                    state = "cancelled"
                elif not condition(stages[spec["stage"]].get("when"), run["context"]) or not condition(spec["when"], run["context"]):
                    state = "skipped"
                else:
                    state = readiness(spec["needs"], statuses)
                if state != task["state"]:
                    db.execute("UPDATE tasks SET state=? WHERE run_id=? AND id=?", (state, run_id, task["id"]))
                    self._event(db, run_id, task["id"], "task.state", {"from": task["state"], "state": state})
        return self.tasks(run_id)

    def claim(self, run_id, task_id, owner, lease_seconds=30):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM tasks WHERE run_id=? AND id=?", (run_id, task_id)).fetchone()
            if row is None or row["state"] != "ready" or row["attempts"] >= row["max_attempts"]:
                return None
            if db.execute("SELECT cancelled FROM runs WHERE id=?", (run_id,)).fetchone()[0]:
                return None
            number = row["attempts"] + 1
            attempt = uuid.uuid4().hex
            db.execute("UPDATE tasks SET state='running',owner=?,lease=?,attempts=? WHERE run_id=? AND id=?",
                       (owner, time.time() + lease_seconds, number, run_id, task_id))
            db.execute("INSERT INTO attempts(id,run_id,task_id,number,started,state) VALUES(?,?,?,?,?,'running')",
                       (attempt, run_id, task_id, number, time.time()))
            self._event(db, run_id, task_id, "task.claimed", {"owner": owner, "attempt": attempt})
        return attempt

    def heartbeat(self, run_id, task_id, owner, pid=None, identity=None):
        with self.connect() as db:
            changed = db.execute("UPDATE tasks SET lease=?,pid=COALESCE(?,pid),process_identity=COALESCE(?,process_identity) "
                                 "WHERE run_id=? AND id=? AND owner=? AND state='running'",
                                 (time.time() + 30, pid, identity, run_id, task_id, owner)).rowcount
        return changed == 1

    def finish(self, run_id, task_id, owner, attempt, state, evidence):
        if state not in {"succeeded", "failed", "cancelled"}:
            raise ValueError("invalid worker completion state")
        if state == "succeeded" and evidence.get("exit_code") != 0:
            raise ValueError("success requires captured zero exit code")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            attempt_row = db.execute("SELECT state FROM attempts WHERE id=? AND run_id=? AND task_id=?",
                                     (attempt, run_id, task_id)).fetchone()
            if attempt_row is None or attempt_row["state"] != "running":
                raise ValueError("attempt does not own this task completion")
            if db.execute("SELECT cancelled FROM runs WHERE id=?", (run_id,)).fetchone()[0]:
                state = "cancelled"
            changed = db.execute("UPDATE tasks SET state=?,result=?,lease=NULL,pid=NULL,process_identity=NULL "
                                 "WHERE run_id=? AND id=? AND owner=? AND state='running'",
                                 (state, json.dumps(evidence), run_id, task_id, owner)).rowcount
            if changed != 1:
                raise ValueError("lost task ownership")
            db.execute("UPDATE attempts SET state=?,finished=?,evidence=? WHERE id=? AND state='running'",
                       (state, time.time(), json.dumps(evidence), attempt))
            self._event(db, run_id, task_id, "task.finished", {"state": state, "attempt": attempt, "evidence": evidence})

    def retry(self, run_id, task_id):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT state,attempts,max_attempts FROM tasks WHERE run_id=? AND id=?",
                             (run_id, task_id)).fetchone()
            if not row or row["state"] not in {"failed", "blocked", "cancelled"} or row["attempts"] >= row["max_attempts"]:
                raise ValueError("task not retryable or attempt budget exhausted")
            db.execute("UPDATE tasks SET state='pending',result=NULL,owner=NULL,lease=NULL,pid=NULL,process_identity=NULL "
                       "WHERE run_id=? AND id=?", (run_id, task_id))
            # Failed dependency descendants must be reconsidered without erasing executed evidence.
            db.execute("UPDATE tasks SET state='pending' WHERE run_id=? AND "
                       "(state='blocked' OR (state='cancelled' AND attempts=0))", (run_id,))
            db.execute("UPDATE runs SET state='pending',cancelled=0,updated=? WHERE id=?", (time.time(), run_id))
            self._event(db, run_id, task_id, "task.retry", {})

    def cancel(self, run_id):
        self.run(run_id)
        with self.connect() as db:
            db.execute("UPDATE runs SET cancelled=1,state='cancelled',updated=? WHERE id=?", (time.time(), run_id))
            db.execute("UPDATE tasks SET state='cancelled' WHERE run_id=? AND state IN ('pending','ready','blocked')", (run_id,))
            self._event(db, run_id, None, "run.cancel_requested", {})

    def acquire_lease(self, resource, owner, seconds=30):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT owner,expires FROM leases WHERE resource=?", (resource,)).fetchone()
            if row and row["owner"] != owner and row["expires"] > time.time():
                return False
            db.execute("INSERT OR REPLACE INTO leases VALUES(?,?,?)", (resource, owner, time.time() + seconds))
        return True

    def release_lease(self, resource, owner):
        with self.connect() as db:
            db.execute("DELETE FROM leases WHERE resource=? AND owner=?", (resource, owner))

    def recover(self, run_id):
        from .workers import process_alive
        recovered = []
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            for task in db.execute("SELECT * FROM tasks WHERE run_id=? AND state='running'", (run_id,)).fetchall():
                if task["lease"] and task["lease"] > time.time():
                    continue
                if task["pid"] and process_alive(task["pid"], task["process_identity"]):
                    continue  # Never reclaim a live orphan. Cancel/stop it explicitly first.
                evidence = {"error": "worker/coordinator crashed; lease expired", "exit_code": None}
                db.execute("UPDATE tasks SET state='failed',result=?,owner=NULL,lease=NULL,pid=NULL WHERE run_id=? AND id=?",
                           (json.dumps(evidence), run_id, task["id"]))
                db.execute("UPDATE attempts SET state='failed',finished=?,evidence=? WHERE run_id=? AND task_id=? AND state='running'",
                           (time.time(), json.dumps(evidence), run_id, task["id"]))
                self._event(db, run_id, task["id"], "task.recovered", evidence)
                recovered.append(task["id"])
        return recovered

    def assert_deliverable(self, run_id):
        from .workers import git
        run = self.run(run_id)
        tasks = self.validate_tasks(run_id)
        if run["cancelled"] or any(t["state"] not in {"succeeded", "skipped"} for t in tasks):
            raise ValueError("delivery blocked by incomplete or failed tasks")
        for task in tasks:
            if task["state"] != "succeeded":
                continue
            evidence = task["result"] or {}
            if evidence.get("exit_code") != 0 or not evidence.get("worktree") or not evidence.get("revision"):
                raise ValueError("delivery requires complete executed task evidence")
            try:
                if git(evidence["worktree"], "rev-parse", "HEAD") != evidence["revision"] or git(evidence["worktree"], "status", "--porcelain"):
                    raise ValueError("worker output changed after recorded verification")
                log_hash = hashlib.sha256(Path(evidence["log"]).read_bytes()).hexdigest()
                if log_hash != evidence.get("log_sha256"):
                    raise ValueError("task evidence log changed after execution")
            except (OSError, RuntimeError, KeyError) as exc:
                raise ValueError("delivery evidence unavailable or inconsistent") from exc
        selected = {s["id"] for s in run["recipe"]["stages"] if condition(s.get("when"), run["context"])}
        for stage in selected - {"deliver"}:
            if not any(t["spec"]["stage"] == stage and t["state"] == "succeeded" for t in tasks):
                raise ValueError(f"delivery blocked by unverified selected stage: {stage}")
        writes = [t for t in tasks if t["spec"]["kind"] == "execute" and t["state"] == "succeeded"]
        requires_review = run["context"].get("policy", {}).get("requires_review", True)
        if writes:
            checks = [t for t in tasks if t["spec"]["kind"] == "verify" and t["state"] == "succeeded"]
            if not checks or any(not t["result"] or t["result"].get("exit_code") != 0 for t in checks):
                raise ValueError("delivery requires actual successful verification")
            # Check every change is an ancestor of a verification task, so independent untested work cannot slip through.
            by_id = {t["id"]: t for t in tasks}

            def ancestors(task):
                result = set()
                for name in task["spec"]["needs"]:
                    name = name.rstrip("?")
                    result.add(name)
                    result.update(ancestors(by_id[name]))
                return result

            covered = set().union(*(ancestors(t) for t in checks))
            if any(t["id"] not in covered for t in writes):
                raise ValueError("delivery contains an unverified change")
            if len({t["spec"]["repo"] for t in writes}) > 1:
                if not any(t["spec"].get("integration") and {w["id"] for w in writes} <= ancestors(t) for t in checks):
                    raise ValueError("multi-repository delivery requires aggregate integration verification")
                requires_review = True
            if requires_review:
                reviews = [t for t in tasks if t["spec"]["kind"] == "review" and t["state"] == "succeeded"]
                reviewed = set().union(*(ancestors(t) for t in reviews)) if reviews else set()
                if any(t["id"] not in reviewed for t in checks):
                    raise ValueError("aggregate review required after verification")
        return True
