"""Explicit local runtime entry points; no installation hook starts this CLI."""

import argparse
import json
from pathlib import Path
import signal
import sys
import time

from .runtime import Store
from .watch import Watcher
from .workers import Coordinator, probe_provider


def read_json(path):
    data = Path(path)
    if data.stat().st_size > 1048576:
        raise ValueError("runtime plan/config exceeds 1 MiB")
    return json.loads(data.read_text())


def main(argv=None):
    parser = argparse.ArgumentParser(description="SDLCkit durable local runtime (workers and watches are opt-in)")
    parser.add_argument("--db", default=".sdlc/runs/runtime.sqlite3")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create", help="record a JSON run plan without executing it")
    create.add_argument("--plan", required=True)
    status = sub.add_parser("status")
    status.add_argument("run_id", nargs="?")
    history = sub.add_parser("history")
    history.add_argument("run_id", nargs="?")
    execute = sub.add_parser("execute", help="execute a previously reviewed immutable command plan")
    execute.add_argument("run_id")
    execute.add_argument("--approve-local", action="store_true")
    execute.add_argument("--approve-external", action="store_true")
    execute.add_argument("--approve-provider", action="store_true")
    execute.add_argument("--approve-effect", action="append", default=[],
                         choices=["package_install", "migration", "data_change", "infrastructure_change", "high_risk_change"])
    execute.add_argument("--max-workers", type=int, default=1)
    execute.add_argument("--parallel", action="store_true")
    execute.add_argument("--state-root")
    retry = sub.add_parser("retry")
    retry.add_argument("run_id")
    retry.add_argument("task_id")
    for name in ("cancel", "stop", "recover", "delivery-gate"):
        command = sub.add_parser(name)
        command.add_argument("run_id")
    probe = sub.add_parser("probe")
    probe.add_argument("provider", choices=["codex", "claude", "opencode", "cursor"])
    register = sub.add_parser("watch-register", help="store fixed approved scope; remains disabled")
    register.add_argument("watch_id")
    register.add_argument("--config", required=True)
    register.add_argument("--approve-local", action="store_true")
    register.add_argument("--approve-provider", action="store_true")
    register.add_argument("--approve-external", action="store_true")
    register.add_argument("--approve-effect", action="append", default=[],
                          choices=["package_install", "migration", "data_change", "infrastructure_change", "high_risk_change"])
    for name in ("watch-enable", "watch-disable", "watch-status", "watch-poll", "watch-dispatch"):
        command = sub.add_parser(name)
        command.add_argument("watch_id")
    enqueue = sub.add_parser("watch-enqueue")
    enqueue.add_argument("watch_id")
    enqueue.add_argument("--event", required=True)
    serve = sub.add_parser("watch-serve", help="foreground polling/scheduler; Ctrl-C stops launches")
    serve.add_argument("watch_id")
    serve.add_argument("--once", action="store_true")
    webhook = sub.add_parser("webhook-serve", help="foreground authenticated localhost intake, never executes events")
    webhook.add_argument("watch_id")
    webhook.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    try:
        if args.command == "probe":
            result = probe_provider(args.provider)
            print(json.dumps(result, indent=2))
            return 0 if result["available"] else 1
        store = Store(args.db)
        watcher = Watcher(store)
        result = None
        if args.command == "create":
            plan = read_json(args.plan)
            if set(plan) - {"work_id", "run_id", "recipe", "context", "tasks"}:
                raise ValueError(f"unsupported run options/budgets: {sorted(set(plan) - {'work_id', 'run_id', 'recipe', 'context', 'tasks'})}")
            run_id = store.create_run(plan["work_id"], plan["recipe"], plan.get("context"), plan.get("run_id"))
            try:
                for task in plan["tasks"]:
                    task = dict(task)
                    task_id = task.pop("id")
                    store.add_task(run_id, task_id, **task)
                store.validate_tasks(run_id)
            except Exception:
                store.set_run_state(run_id, "blocked")
                raise
            result = {"run_id": run_id, "state": "pending", "tasks": store.tasks(run_id)}
        elif args.command == "execute":
            if args.max_workers > 1 and not args.parallel:
                raise PermissionError("parallel execution requires explicit --parallel")
            coordinator = Coordinator(store, args.state_root, args.max_workers)
            previous = signal.signal(signal.SIGINT, lambda *_: coordinator.stop())
            try:
                result = coordinator.run(args.run_id, args.approve_local, args.approve_external, args.approve_provider,
                                         approved_effects=args.approve_effect)
            finally:
                signal.signal(signal.SIGINT, previous)
            print(json.dumps(result, indent=2))
            return 0 if result["state"] in {"verified", "delivered"} else 1
        elif args.command == "status":
            if args.run_id:
                result = {"run": store.run(args.run_id), "tasks": store.tasks(args.run_id)}
            else:
                with store.connect() as db:
                    result = [dict(row) for row in db.execute("SELECT id,work_id,state,created,updated FROM runs ORDER BY created")]
        elif args.command == "history":
            result = store.history(args.run_id)
        elif args.command == "retry":
            store.retry(args.run_id, args.task_id)
            result = {"run_id": args.run_id, "retry": args.task_id}
        elif args.command in {"cancel", "stop"}:
            Coordinator(store).stop_orphans(args.run_id)
            result = store.run(args.run_id)
        elif args.command == "recover":
            result = {"recovered": store.recover(args.run_id)}
        elif args.command == "delivery-gate":
            result = {"deliverable": store.assert_deliverable(args.run_id)}
        elif args.command == "watch-register":
            result = watcher.configure(args.watch_id, read_json(args.config), args.approve_local,
                                       args.approve_provider, args.approve_external, args.approve_effect)
        elif args.command in {"watch-enable", "watch-disable"}:
            watcher.enable(args.watch_id, args.command == "watch-enable")
            result = watcher.get(args.watch_id)
        elif args.command == "watch-status":
            result = {"watch": watcher.get(args.watch_id), "queue": watcher.queue(args.watch_id)}
        elif args.command == "watch-enqueue":
            result = {"queue_id": watcher.enqueue(args.watch_id, read_json(args.event))}
        elif args.command == "watch-poll":
            result = {"enqueued": watcher.poll(args.watch_id)}
        elif args.command == "watch-dispatch":
            result = watcher.dispatch_once(args.watch_id)
        elif args.command == "watch-serve":
            while watcher.get(args.watch_id)["enabled"]:
                watcher.poll(args.watch_id)
                result = watcher.dispatch_once(args.watch_id)
                if args.once:
                    break
                time.sleep(min(watcher.get(args.watch_id)["config"]["poll_interval"], 1))
        elif args.command == "webhook-serve":
            server = watcher.server(args.watch_id, args.port)
            print(json.dumps({"listen": f"http://127.0.0.1:{server.server_port}/events", "executes": False}), flush=True)
            try:
                server.serve_forever(poll_interval=0.25)
            finally:
                server.server_close()
        if result is not None:
            print(json.dumps(result, indent=2))
        return 0
    except KeyboardInterrupt:
        print("runtime stopped; durable state retained", file=sys.stderr)
        return 130
    except (ValueError, TypeError, KeyError, OSError, RuntimeError, PermissionError) as exc:
        print(f"runtime: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
