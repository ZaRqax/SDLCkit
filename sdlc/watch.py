"""Explicitly enabled polling and authenticated local webhook intake.

Events are lower-trust requirements. They cannot supply executable commands;
only the user-approved stored task template can launch a worker.
"""

import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import threading
import time

from .runtime import identifier
from .workers import Coordinator, validate_argv, RISKY
from .workflows import validate_recipe

MAX_EVENT_BYTES = 262144


class Watcher:
    def __init__(self, store):
        self.store = store

    def _authorize_poll(self, config, approved_local):
        from .config import load_for_target
        from .policy import classify_command, require_effect
        argv = validate_argv(config["poll_argv"])
        if config.get("poll_effect") != "read":
            raise ValueError("polling adapter must declare read-only effect")
        observed = classify_command(shlex.join(argv))
        if observed not in {"read", "observe", "local_read", "inspect", "search", "local_process"}:
            raise PermissionError(f"read-only polling refuses observed {observed} effect")
        # The adapter may read any registered project; every current scope must permit it.
        for repo in config["repositories"]:
            effective = load_for_target(repo)
            for effect in {"read", "local_process", observed}:
                require_effect(effect, config=effective, approved=approved_local, scope=repo)
        return observed

    def configure(self, watch_id, config, approved_local=False, approved_provider=False, approved_external=False,
                  approved_effects=()):
        identifier(watch_id)
        if len(watch_id) > 80:
            raise ValueError("watch ID exceeds 80 characters")
        config = json.loads(json.dumps(config))
        supported = {"template", "repositories", "poll_argv", "poll_effect", "max_workers", "max_queue",
                     "max_runs_per_day", "poll_interval", "max_database_bytes", "poll_timeout",
                     "max_run_seconds", "eligibility", "webhook_secret_env"}
        if set(config) - supported:
            raise ValueError(f"unsupported watch options/budgets: {sorted(set(config) - supported)}")
        if not approved_local:
            raise PermissionError("watch registration requires explicit approval of the fixed local command template")
        if not isinstance(config.get("template"), dict) or not isinstance(config["template"].get("tasks"), list):
            raise ValueError("watch requires a fixed run template")
        template = config["template"]
        if set(template) - {"recipe", "context", "tasks"}:
            raise ValueError("unsupported watch template options/budgets")
        validate_recipe(template.get("recipe"))
        if not set(approved_effects) <= RISKY:
            raise ValueError("invalid risky effect approval")
        if (template.get("context", {}).get("task", {}).get("high_risk") or template["recipe"].get("id") == "high-risk") and "high_risk_change" not in approved_effects:
            raise PermissionError("high-risk watch requires explicit scoped high_risk_change approval")
        if not template["tasks"]:
            raise ValueError("watch template has no tasks")
        roots = config.get("repositories")
        if not isinstance(roots, list) or not roots:
            raise ValueError("watch must allowlist exact repository paths")
        roots = [str(Path(p).resolve(strict=True)) for p in roots]
        config["repositories"] = roots
        for task in template["tasks"]:
            if str(Path(task["repo"]).resolve(strict=True)) not in roots:
                raise ValueError("task repository outside watch scope")
            validate_argv(task.get("argv"), task.get("provider", "command"))
            if task.get("provider", "command") != "command" and not approved_provider:
                raise PermissionError("watch provider automation requires explicit approval")
            if "external_write" in task.get("effects", []) and not approved_external:
                raise PermissionError("watch external effects require explicit scoped approval")
        if config.get("poll_argv"):
            self._authorize_poll(config, approved_local)
        limits = {"max_workers": (1, 8, 1), "max_queue": (1, 10000, 100),
                  "max_runs_per_day": (1, 1000, 10), "poll_interval": (1, 86400, 60),
                  "max_database_bytes": (1048576, 1073741824, 67108864),
                  "poll_timeout": (1, 300, 30), "max_run_seconds": (1, 86400, 3600)}
        for key, (minimum, maximum, default) in limits.items():
            value = config.setdefault(key, default)
            if not isinstance(value, (int, float)) or not minimum <= value <= maximum:
                raise ValueError(f"invalid watch resource limit: {key}")
        eligible = config.setdefault("eligibility", {})
        if not isinstance(eligible, dict) or not set(eligible) <= {"required_labels", "allowed_projects"}:
            raise ValueError("unsupported eligibility rules")
        if any(not isinstance(v, list) or any(not isinstance(x, str) for x in v) for v in eligible.values()):
            raise ValueError("eligibility values must be lists of strings")
        secret_env = config.setdefault("webhook_secret_env", "SDLC_WEBHOOK_SECRET")
        if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,100}", secret_env):
            raise ValueError("webhook secret must reference an environment variable")
        config["approval"] = {"local": approved_local, "provider": approved_provider, "external": approved_external,
                              "effects": list(approved_effects)}
        # Template/resource updates intentionally disable the watcher and require explicit re-enable.
        with self.store.connect() as db:
            db.execute("INSERT INTO watches(id,enabled,config,updated) VALUES(?,0,?,?) "
                       "ON CONFLICT(id) DO UPDATE SET enabled=0,config=excluded.config,updated=excluded.updated",
                       (watch_id, json.dumps(config), time.time()))
            self.store._event(db, None, None, "watch.configured", {"watch_id": watch_id, "approval": config["approval"]})
        return self.get(watch_id)

    def get(self, watch_id):
        with self.store.connect() as db:
            row = db.execute("SELECT * FROM watches WHERE id=?", (watch_id,)).fetchone()
        if row is None:
            raise ValueError("unknown watch")
        return dict(row) | {"config": json.loads(row["config"]), "enabled": bool(row["enabled"])}

    def enable(self, watch_id, enabled):
        self.get(watch_id)
        with self.store.connect() as db:
            db.execute("UPDATE watches SET enabled=?,updated=? WHERE id=?", (int(enabled), time.time(), watch_id))
            self.store._event(db, None, None, "watch.enabled" if enabled else "watch.disabled", {"watch_id": watch_id})

    def eligible(self, payload, config):
        if not isinstance(payload, dict) or not isinstance(payload.get("id"), str) or not payload["id"]:
            raise ValueError("source event requires stable id")
        if len(payload["id"]) > 500 or len(json.dumps(payload).encode()) > MAX_EVENT_BYTES:
            raise ValueError("source event exceeds bounds")
        rules = config["eligibility"]
        labels = payload.get("labels", [])
        if not isinstance(labels, list) or any(not isinstance(x, str) for x in labels):
            raise ValueError("invalid event labels")
        if not set(rules.get("required_labels", [])) <= set(labels):
            return False
        if rules.get("allowed_projects") and payload.get("project") not in rules["allowed_projects"]:
            return False
        return True

    def enqueue(self, watch_id, payload, receipt=None):
        watch = self.get(watch_id)
        config = watch["config"]
        if not self.eligible(payload, config):
            self.store.event(None, None, "watch.ineligible", {"watch_id": watch_id, "source_id": payload["id"]})
            return None
        dedup = hashlib.sha256((payload["id"] + ":" + str(payload.get("revision", ""))).encode()).hexdigest()
        database_bytes = sum(p.stat().st_size for p in [self.store.path, Path(str(self.store.path) + "-wal")]
                             if p.exists())
        if database_bytes > config["max_database_bytes"]:
            raise ValueError("watch database budget exceeded")
        with self.store.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            # Disabled intake rejects new events; disabling never deletes queued work/state.
            if not db.execute("SELECT enabled FROM watches WHERE id=?", (watch_id,)).fetchone()[0]:
                raise PermissionError("watch is disabled")
            if receipt:
                try:
                    db.execute("INSERT INTO webhook_receipts VALUES(?,?,?)", (watch_id, receipt, time.time()))
                except Exception as exc:
                    raise PermissionError("webhook replay rejected") from exc
            existing = db.execute("SELECT id FROM queue WHERE watch_id=? AND dedup=?", (watch_id, dedup)).fetchone()
            if existing:
                return existing[0]
            count = db.execute("SELECT COUNT(*) FROM queue WHERE watch_id=? AND state IN ('queued','running','starting')",
                               (watch_id,)).fetchone()[0]
            if count >= config["max_queue"]:
                raise ValueError("watch queue budget exceeded")
            result = db.execute("INSERT INTO queue(watch_id,dedup,payload,state,created) VALUES(?,?,?,'queued',?)",
                                (watch_id, dedup, json.dumps(payload), time.time()))
            self.store._event(db, None, None, "watch.enqueued", {"watch_id": watch_id, "queue_id": result.lastrowid,
                                                               "source_id": payload["id"], "revision": payload.get("revision")})
            return result.lastrowid

    def poll(self, watch_id):
        watch = self.get(watch_id)
        if not watch["enabled"]:
            return []
        config = watch["config"]
        argv = config.get("poll_argv")
        if not argv:
            return []
        if watch["last_poll"] and time.time() - watch["last_poll"] < config["poll_interval"]:
            return []
        owner = f"poll-{os.getpid()}-{time.time_ns()}"
        resource = f"watch-poll:{watch_id}"
        if not self.store.acquire_lease(resource, owner, config["poll_timeout"] + 10):
            return []
        try:
            observed = self._authorize_poll(config, config["approval"]["local"])
            if not self.get(watch_id)["enabled"]:
                return []
            self.store.event(None, None, "watch.poll.authorized", {"watch_id": watch_id, "observed_effect": observed,
                                                                   "scopes": config["repositories"]})
            # Retain at most the source bound; no unbounded tempfile or undrained pipe.
            proc = None
            reader = None
            content = bytearray()
            overflow = threading.Event()
            started = time.monotonic()
            error = None
            try:
                from .workers import terminate_group
                proc = subprocess.Popen(argv, cwd=config["repositories"][0], stdin=subprocess.DEVNULL,
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)

                def drain():
                    while True:
                        chunk = os.read(proc.stdout.fileno(), 65536)
                        if not chunk:
                            break
                        remaining = max(0, MAX_EVENT_BYTES - len(content))
                        content.extend(chunk[:remaining])
                        if len(chunk) > remaining:
                            overflow.set()

                reader = threading.Thread(target=drain, daemon=True)
                reader.start()
                while proc.poll() is None:
                    if time.monotonic() - started > config["poll_timeout"] or overflow.is_set():
                        error = "poll adapter exceeded output/time budget"
                        terminate_group(proc.pid)
                        proc.wait(timeout=5)
                        raise ValueError(error)
                    time.sleep(0.05)
                proc.wait(timeout=5)
                # A completed leader must not leave children running with inherited output handles.
                terminate_group(proc.pid)
                reader.join(timeout=2)
                if reader.is_alive():
                    raise ValueError("poll adapter output reader did not finish")
                if overflow.is_set():
                    raise ValueError("poll adapter output budget exceeded")
                if proc.returncode:
                    raise RuntimeError(f"poll adapter failed with exit {proc.returncode}")
            except Exception as exc:
                error = str(exc)
                raise
            finally:
                if proc is not None:
                    terminate_group(proc.pid)
                    proc.wait(timeout=5)
                    if reader is not None:
                        reader.join(timeout=2)
                    proc.stdout.close()
                self.store.event(None, None, "watch.poll", {"watch_id": watch_id, "argv": argv,
                                                            "exit_code": proc.returncode if proc is not None else None,
                                                            "sha256": hashlib.sha256(content).hexdigest(),
                                                            "captured_bytes": len(content), "truncated": overflow.is_set(),
                                                            "duration": time.monotonic() - started, "error": error})
            events = json.loads(content)
            if not isinstance(events, list) or len(events) > config["max_queue"]:
                raise ValueError("poll adapter must return bounded JSON event list")
            queued = [self.enqueue(watch_id, payload) for payload in events]
            with self.store.connect() as db:
                db.execute("UPDATE watches SET last_poll=? WHERE id=?", (time.time(), watch_id))
            return queued
        finally:
            self.store.release_lease(resource, owner)

    def queue(self, watch_id):
        with self.store.connect() as db:
            return [dict(row) | {"payload": json.loads(row["payload"])} for row in
                    db.execute("SELECT * FROM queue WHERE watch_id=? ORDER BY id", (watch_id,))]

    def dispatch_once(self, watch_id):
        watch = self.get(watch_id)
        if not watch["enabled"]:
            return None
        config = watch["config"]
        owner = f"watch-{os.getpid()}-{time.time_ns()}"
        resource = f"watch-dispatch:{watch_id}"
        if not self.store.acquire_lease(resource, owner, config["max_run_seconds"] + 30):
            return None
        try:
            with self.store.connect() as db:
                db.execute("BEGIN IMMEDIATE")
                entry = db.execute("SELECT * FROM queue WHERE watch_id=? AND state IN ('queued','starting','running') ORDER BY id LIMIT 1",
                                   (watch_id,)).fetchone()
                if entry is None:
                    return None
                count = db.execute("SELECT COUNT(*) FROM queue q JOIN runs r ON q.run_id=r.id "
                                   "WHERE q.watch_id=? AND r.created>?", (watch_id, time.time() - 86400)).fetchone()[0]
                if entry["run_id"] is None and count >= config["max_runs_per_day"]:
                    raise ValueError("watch daily run budget exhausted")
                run_id = f"watch-{watch_id}-{entry['id']}"
                db.execute("UPDATE queue SET state='starting',run_id=? WHERE id=?", (run_id, entry["id"]))
            template = config["template"]
            try:
                run = self.store.run(run_id)
            except ValueError:
                context = template.get("context") or {"task": {"complexity": "standard", "cross_repo": False,
                                                               "investigation": False, "high_risk": False},
                                                      "policy": {"requires_review": True}}
                context = dict(context, work_item=json.loads(entry["payload"]))
                self.store.create_run(run_id, template["recipe"], context, run_id=run_id)
                run = self.store.run(run_id)
            # Resume interrupted task construction without recreating tasks or another run.
            if run["state"] == "pending":
                existing = {t["id"] for t in self.store.tasks(run_id)}
                for task in template["tasks"]:
                    task = dict(task)
                    task_id = task.pop("id")
                    task["timeout"] = min(task.get("timeout", 600), config["max_run_seconds"])
                    if task_id not in existing:
                        self.store.add_task(run_id, task_id, **task)
            self.store.event(run_id, None, "watch.source", {"watch_id": watch_id,
                                                          "source": json.loads(entry["payload"]), "trust": "untrusted_data"})
            with self.store.connect() as db:
                db.execute("UPDATE queue SET state='running' WHERE id=?", (entry["id"],))
            start = time.monotonic()

            def guard():
                return self.get(watch_id)["enabled"] and time.monotonic() - start < config["max_run_seconds"]

            coordinator = Coordinator(self.store, max_workers=config["max_workers"])
            # Duration bound also stops already-running workers, unlike watch disable (new launches only).
            import threading
            timer = threading.Timer(config["max_run_seconds"], coordinator.stop)
            timer.daemon = True
            timer.start()
            try:
                result = coordinator.run(run_id, approved_local=config["approval"]["local"],
                                         approved_provider=config["approval"]["provider"],
                                         approved_external=config["approval"]["external"], launch_guard=guard,
                                         approved_effects=config["approval"].get("effects", []))
            finally:
                timer.cancel()
            with self.store.connect() as db:
                state = "completed" if result["state"] in {"verified", "delivered"} else "failed"
                db.execute("UPDATE queue SET state=? WHERE id=?", (state, entry["id"]))
            return result
        finally:
            self.store.release_lease(resource, owner)

    def authenticate(self, watch_id, body, timestamp, nonce, signature):
        config = self.get(watch_id)["config"]
        secret = os.environ.get(config["webhook_secret_env"], "")
        if len(secret) < 32:
            raise PermissionError("webhook secret must contain at least 32 characters")
        if not re.fullmatch(r"[A-Za-z0-9_-]{16,100}", nonce or ""):
            raise PermissionError("invalid webhook nonce")
        try:
            fresh = abs(time.time() - int(timestamp)) <= 300
        except (ValueError, TypeError):
            fresh = False
        expected = hmac.new(secret.encode(), f"{timestamp}.{nonce}.".encode() + body, hashlib.sha256).hexdigest()
        if not fresh or not hmac.compare_digest(expected, signature or ""):
            raise PermissionError("invalid or expired webhook signature")
        if len(body) > MAX_EVENT_BYTES:
            raise ValueError("webhook event too large")
        return self.enqueue(watch_id, json.loads(body), receipt=nonce)

    def server(self, watch_id, port=0, host="127.0.0.1"):
        if host != "127.0.0.1":
            raise ValueError("webhook listener must bind to 127.0.0.1; use an authenticated proxy for remote intake")
        self.get(watch_id)
        watcher = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_POST(self):
                code, data = 200, {}
                try:
                    if self.path != "/events":
                        raise ValueError("unknown webhook path")
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= MAX_EVENT_BYTES:
                        raise ValueError("invalid body size")
                    self.connection.settimeout(5)
                    body = self.rfile.read(length)
                    data["queue_id"] = watcher.authenticate(watch_id, body, self.headers.get("X-SDLC-Timestamp"),
                                                             self.headers.get("X-SDLC-Nonce"),
                                                             self.headers.get("X-SDLC-Signature"))
                except PermissionError as exc:
                    code, data = 403, {"error": str(exc)}
                except (ValueError, OSError) as exc:
                    code, data = 400, {"error": str(exc)}
                content = json.dumps(data).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)

        return HTTPServer((host, port), Handler)
