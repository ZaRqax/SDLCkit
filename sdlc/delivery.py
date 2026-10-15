"""Local delivery and explicitly authorized, reconciled GitHub/GitLab publication."""

import argparse
import json
from pathlib import Path
import re
import tempfile
from urllib.parse import quote, urlencode, urlparse

from .storage import atomic_json, command, confined, digest, exclusive, secret_path

KINDS = ("report", "working_tree", "patch", "commit", "local_branch", "github_pr", "gitlab_mr")


def git(repo, *args, allowed=(0,)):
    return command(["git", "--literal-pathspecs", "-C", str(repo), *args], allowed=allowed)


def metadata_root(repo):
    root = Path(git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir").decode().strip()).resolve()
    return root


def content_is_secret(content):
    return bool(re.search(rb"(?m)^-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----\r?$|\b(?:ghp_|github_pat_|sk-proj-)[A-Za-z0-9_]{20,}", content))


def audit_path(path, config):
    from .policy import generated_path
    if path.startswith(("-", ":")) or path == "." or Path(path).is_absolute() or ".." in Path(path).parts:
        raise ValueError("delivery paths must be explicit literal relative file names")
    if secret_path(path) or runtime_path(path):
        raise PermissionError("delivery includes a secret or local runtime state path")
    if generated_path(path, config) and not config.get("verification", {}).get("codegen_verified", False):
        raise PermissionError("generated paths require recorded code-generation verification")


def audit_commits(repo, baseline, revision, config):
    commits = git(repo, "rev-list", "--max-count=1001", baseline + ".." + revision).decode().splitlines()
    if len(commits) > 1000:
        raise ValueError("publication history exceeds 1000 commits; prepare a smaller reviewed branch")
    for commit in commits:
        names = git(repo, "diff-tree", "-m", "--root", "--no-commit-id", "--name-only", "-r", "-z", commit).split(b"\0")
        for raw in set(names) - {b""}:
            path = raw.decode()
            audit_path(path, config)
            object_name = commit + ":" + path
            # Deleted files have no blob in this commit; the earlier commits are audited separately.
            kind = git(repo, "cat-file", "-t", object_name, allowed=(0, 128)).decode().strip()
            if kind == "blob":
                size = git(repo, "cat-file", "-s", object_name).decode().strip()
                if int(size) > 16 * 1024 * 1024:
                    raise ValueError("publication blob exceeds bounded secret inspection limit")
                if content_is_secret(git(repo, "cat-file", "blob", object_name)):
                    raise PermissionError("publication history contains secret-like content")


def repository(path):
    root = Path(git(path, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    if Path(path).resolve() != root:
        raise ValueError("delivery must target the repository root")
    return root


def safe_ref(repo, ref):
    if not ref or ref.startswith("-"):
        raise ValueError("missing or invalid branch")
    git(repo, "check-ref-format", "--branch", ref)
    return ref


def changed_paths(repo, since=None):
    tracked = git(repo, "diff", "--name-only", "-z", since or "HEAD").split(b"\0")
    untracked = git(repo, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0")
    return sorted({p.decode() for p in tracked + untracked if p and not runtime_path(p.decode())})


def runtime_path(path):
    parts = Path(path).parts
    if ".sdlc" not in parts:
        return False
    suffix = parts[parts.index(".sdlc") + 1:]
    return bool(suffix and (suffix[0] in {"runs", "deliveries", "logs", "backups", "state", "runtime"}
                           or suffix[-1] in {"local.yaml", "local.json", "generated-manifest.json", "install-journal.json"}
                           or suffix[-1].endswith((".sqlite", ".db", ".lock"))))


def selected_paths(repo, paths=None, config=None, since=None):
    config = config or {}
    selected = paths if paths is not None else changed_paths(repo, since)
    result = []
    for path in selected:
        audit_path(path, config)
        resolved = confined(repo, path)
        if resolved.is_dir():
            raise ValueError("delivery paths must name files, not directories")
        if resolved.is_file() and not resolved.is_symlink():
            if resolved.stat().st_size > 16 * 1024 * 1024:
                raise ValueError("selected file exceeds bounded secret inspection limit")
            if content_is_secret(resolved.read_bytes()):
                raise PermissionError("delivery file contains secret-like content")
        result.append(path)
    return sorted(set(result))


def patch_bytes(repo, paths, since=None):
    if not paths:
        return b""
    patch = git(repo, "diff", "--binary", since or "HEAD", "--", *paths)
    untracked = set(x.decode() for x in git(repo, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0") if x)
    for path in paths:
        if path in untracked:
            patch += command(["git", "--literal-pathspecs", "diff", "--binary", "--no-index", "--", "/dev/null", path],
                             cwd=repo, allowed=(0, 1))
    return patch


def prepare(repo, kind, work_id, title="", body="", base=None, branch=None, paths=None, config=None, since=None):
    if kind not in KINDS:
        raise ValueError("unsupported delivery target")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,100}", work_id):
        raise ValueError("invalid work ID")
    config = config or {}
    if kind not in config.get("delivery", {}).get("allowed", KINDS):
        raise PermissionError("delivery target is not allowed by effective configuration")
    repo = repository(repo)
    revision = git(repo, "rev-parse", "HEAD").decode().strip()
    if since is not None:
        if kind not in {"patch", "report", "working_tree"} or since.startswith("-"):
            raise ValueError("--since is a committed baseline for local patch/report delivery only")
        since = git(repo, "rev-parse", "--verify", since + "^{commit}").decode().strip()
        git(repo, "merge-base", "--is-ancestor", since, revision)
    current = git(repo, "symbolic-ref", "--quiet", "--short", "HEAD", allowed=(0, 1)).decode().strip()
    branch = safe_ref(repo, branch or (("work/" + work_id) if kind == "local_branch" else current) or ("work/" + work_id))
    remote = kind in {"github_pr", "gitlab_mr"}
    comparison_base = since
    if remote:
        from .policy import evaluate_effect
        if evaluate_effect('external_write', config, scope=str(repo))['decision'] == 'forbidden':
            raise PermissionError('publication is forbidden by effective policy')
        if branch != current:
            raise ValueError("publication branch must be the checked-out branch")
        if changed_paths(repo):
            raise ValueError("publication requires a clean committed working tree")
        base = base or config.get("project", {}).get("branches", {}).get("base")
        if base in {None, "auto"}:
            value = git(repo, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD", allowed=(0, 1)).decode().strip()
            base = value.removeprefix("origin/") if value else None
        if not base:
            raise ValueError("base branch is unknown; specify --base or repository policy")
        safe_ref(repo, base)
        protected = {"main", "master", "develop", base}
        if branch in protected or branch.startswith("release/"):
            raise PermissionError("publication from a protected/base branch is forbidden")
        base_revision = git(repo, "rev-parse", "--verify", f"refs/remotes/origin/{base}^{{commit}}", allowed=(0, 128)).decode().strip()
        if not base_revision:
            base_revision = git(repo, "rev-parse", "--verify", f"refs/heads/{base}^{{commit}}", allowed=(0, 128)).decode().strip()
        if not base_revision:
            raise ValueError("base revision is unavailable locally; fetch/review it before publication")
        comparison_base = git(repo, "merge-base", base_revision, revision).decode().strip()
        audit_commits(repo, comparison_base, revision, config)
        all_paths = changed_paths(repo, comparison_base)
        if paths is not None and sorted(paths) != all_paths:
            raise ValueError("publication includes the entire branch; partial path selection is forbidden")
    chosen = selected_paths(repo, paths, config, comparison_base)
    diff_hash = digest(patch_bytes(repo, chosen, comparison_base))
    identity = "/".join(remote_identity(repo, kind)) if remote else str(metadata_root(repo))
    key = digest(identity + "\n" + work_id + "\n" + kind + "\n" + branch + "\n" + str(base))
    return {
        "schema_version": 1, "idempotency_key": key, "repo": str(repo), "kind": kind,
        "work_id": work_id, "title": title or work_id, "body": body, "base": base,
        "branch": branch, "revision": revision, "paths": chosen, "diff_sha256": diff_hash,
        "marker": f"<!-- sdlckit:{key} -->",
        "since": since,
        "comparison_base": comparison_base,
    }


def validate(prepared, config=None):
    current = prepare(prepared["repo"], prepared["kind"], prepared["work_id"], prepared["title"],
                      prepared["body"], prepared["base"], prepared["branch"], prepared["paths"], config, prepared.get("since"))
    if current != prepared:
        raise ValueError("prepared delivery is stale; prepare and review the current revision again")
    return {"valid": True, "revision": current["revision"], "diff_sha256": current["diff_sha256"]}


def remote_identity(repo, kind):
    raw = git(repo, "remote", "get-url", "origin").decode().strip()
    if raw.startswith("git@"):
        host, path = raw[4:].split(":", 1)
    else:
        parsed = urlparse(raw)
        if parsed.scheme not in {"https", "ssh"} or parsed.password or (parsed.username and parsed.scheme == "https"):
            raise ValueError("origin must be HTTPS or SSH without embedded credentials")
        host, path = parsed.hostname, parsed.path.lstrip("/")
    path = path.removesuffix(".git")
    if not host or not re.fullmatch(r"[A-Za-z0-9._/-]+", path) or ".." in path.split("/"):
        raise ValueError("invalid publication repository identity")
    if kind == "github_pr" and host != "github.com":
        raise ValueError("GitHub Enterprise publication requires an explicit custom delivery adapter")
    return host, path


def reconcile(prepared):
    """Only provider reads; a failed read aborts publication rather than assuming absence."""
    repo = prepared["repo"]
    host, project = remote_identity(repo, prepared["kind"])
    if prepared["kind"] == "github_pr":
        rows = json.loads(command([
            "gh", "pr", "list", "--repo", f"{host}/{project}", "--head", prepared["branch"],
            "--base", prepared["base"], "--state", "all", "--limit", "100", "--json", "url,body,state,headRefOid",
        ], cwd=repo))
        if len(rows) >= 100:
            raise ValueError("publication reconciliation exceeded bounded history; inspect provider manually")
        matches = [row for row in rows if prepared["marker"] in row.get("body", "")]
    else:
        query = urlencode({"scope": "all", "source_branch": prepared["branch"],
                           "target_branch": prepared["base"], "per_page": 100})
        endpoint = f"projects/{quote(project, safe='')}/merge_requests?{query}"
        rows = json.loads(command(["glab", "api", "--hostname", host, endpoint], cwd=repo))
        if len(rows) >= 100:
            raise ValueError("publication reconciliation exceeded bounded history; inspect provider manually")
        matches = [row for row in rows if prepared["marker"] in (row.get("description") or "")]
    if len(matches) > 1:
        raise ValueError("multiple publications share the delivery marker; manual reconciliation required")
    if not matches:
        return None
    row = matches[0]
    return {"url": row.get("url", row.get("web_url")), "state": row.get("state"), "reconciled": True,
            "revision": row.get("headRefOid", row.get("sha"))}


def authorize(effect, config, approved, scope):
    from .policy import require_effect
    require_effect(effect, config=config, approved=approved, scope=scope)


def publish(prepared, config=None, approved_local=False, approved_external=False, output=None,
            message=None, runtime_db=None, run_id=None):
    config = config or {}
    kind, repo = prepared["kind"], Path(prepared["repo"])
    if bool(runtime_db) != bool(run_id):
        raise ValueError("runtime delivery requires both --runtime-db and --run-id")
    store = None
    if runtime_db:
        from .runtime import Store
        store = Store(runtime_db)
        store.assert_deliverable(run_id)
        common = git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir").decode().strip()
        matching = []
        for task in store.tasks(run_id):
            if task["state"] != "succeeded" or task["spec"]["kind"] not in {"verify", "review"}:
                continue
            result = task.get("result") or {}
            if result.get("revision") != prepared["revision"]:
                continue
            original_common = git(task["spec"]["repo"], "rev-parse", "--path-format=absolute", "--git-common-dir").decode().strip()
            if common == original_common:
                matching.append(task)
        if not matching or changed_paths(repo):
            raise ValueError("delivery repository/revision does not match clean verified runtime output")

    def complete(result):
        if store is not None:
            identity = str(metadata_root(repo))
            store.event(run_id, None, 'delivery.published', {'repository': identity, 'result': result})
            required = {str(metadata_root(task['spec']['repo'])) for task in store.tasks(run_id)
                        if task['state'] == 'succeeded' and task['spec']['kind'] == 'execute'}
            delivered = {event['data']['repository'] for event in store.history(run_id)
                         if event['type'] == 'delivery.published'}
            if required and required <= delivered and store.run(run_id)['state'] == 'verified':
                store.set_run_state(run_id, 'delivered')
        return result
    remote = kind in {"github_pr", "gitlab_mr"}
    effect = "external_write" if remote else ("local_write" if kind not in {"report", "working_tree"} else "observe")
    authorize(effect, config, approved_external if remote else approved_local, str(repo))
    if kind in {"report", "working_tree"}:
        validate(prepared, config)
        return complete({"kind": kind, "repo": str(repo), "revision": prepared["revision"],
                         "paths": prepared["paths"], "verified": bool(runtime_db), "publication": None})
    if kind == "patch":
        validate(prepared, config)
        if output is None:
            raise ValueError("patch delivery requires an explicit output path")
        artifact_root = repo
        if runtime_db:
            artifact_root = confined(metadata_root(repo), Path("sdlckit/artifacts") / run_id)
        output = confined(artifact_root, output)
        if secret_path(output.relative_to(artifact_root)):
            raise ValueError("patch output must be a non-secret file")
        data = patch_bytes(repo, prepared["paths"], prepared.get("since"))
        if not data:
            raise ValueError("no changes to export")
        if output.exists():
            if not output.is_file() or output.read_bytes() != data:
                raise ValueError('patch output conflicts with an existing user file')
            return complete({"kind": kind, "path": str(output), "sha256": digest(data), "verified": bool(runtime_db)})
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("xb") as stream:
            stream.write(data)
        return complete({"kind": kind, "path": str(output), "sha256": digest(data), "verified": bool(runtime_db)})
    common_root = metadata_root(repo)
    state_dir = confined(common_root, "sdlckit/deliveries")
    key = prepared["idempotency_key"]
    record_path = confined(common_root, state_dir / (key + ".json"))
    with exclusive(confined(common_root, state_dir / (key + ".lock"))):
        record = json.loads(record_path.read_text()) if record_path.exists() else None
        if record and record.get("status") == "published":
            previous = record.get("prepared", {})
            if not remote:
                same_preparation = previous == prepared
                no_new_work = (prepared["revision"] == record["result"].get("commit")
                               and not prepared["paths"] and not changed_paths(repo))
                if not same_preparation and not no_new_work:
                    raise ValueError("work ID already delivered a different local change; choose a new work ID")
                return complete(record["result"])
        if kind in {"commit", "local_branch"}:
            if record:
                # A commit may have succeeded before the acknowledgement was durable.
                current = git(repo, "rev-parse", "HEAD").decode().strip()
                parent = git(repo, "rev-parse", "HEAD^", allowed=(0, 128)).decode().strip()
                if current != prepared["revision"] and parent == prepared["revision"]:
                    actual = git(repo, "show", "--pretty=", "--name-only", "-z", "HEAD").split(b"\0")
                    committed_hash = digest(git(repo, "diff", "--binary", prepared["revision"], current, "--", *prepared["paths"]))
                    if sorted(x.decode().strip() for x in actual if x.strip()) == prepared["paths"] and committed_hash == prepared["diff_sha256"]:
                        result = {"kind": kind, "commit": current, "branch": prepared["branch"], "reconciled": True}
                        atomic_json(record_path, {"status": "published", "prepared": prepared, "result": result})
                        return complete(result)
                raise ValueError("interrupted local delivery requires manual index/commit reconciliation")
            validate(prepared, config)
            staged = git(repo, "diff", "--cached", "--name-only", "-z")
            if staged:
                raise ValueError("commit delivery requires an empty index; preserve existing staged work")
            if not prepared["paths"]:
                raise ValueError("no changes selected for a commit")
            if kind == "local_branch":
                git(repo, "switch", "-c", prepared["branch"])
            atomic_json(record_path, {"status": "publishing", "prepared": prepared})
            git(repo, "add", "--", *prepared["paths"])
            try:
                command(["git", "-C", str(repo), "commit", "--file", "-"],
                        stdin=(message or prepared["title"]).encode())
            except ValueError:
                # Leave index/worktree intact; the user can inspect a failing hook without data loss.
                raise
            result = {"kind": kind, "commit": git(repo, "rev-parse", "HEAD").decode().strip(),
                      "branch": git(repo, "branch", "--show-current").decode().strip(), "reconciled": False}
        else:
            validate(prepared, config)
            if prepared["kind"].split("_")[0] not in config.get("integrations", {}) or not config["integrations"][kind.split("_")[0]].get("enabled"):
                raise PermissionError("publication provider is disabled")
            existing = reconcile(prepared)
            if existing:
                if not existing.get("revision"):
                    raise ValueError("provider did not return a publication head revision; cannot confirm prepared output")
                if existing['revision'] != prepared['revision']:
                    if str(existing.get("state", "")).lower() not in {"open", "opened"}:
                        raise ValueError("existing publication is closed; choose a new work ID for another change")
                    # Update the existing review branch, without creating another PR/MR.
                    atomic_json(record_path, {"status": "publishing", "prepared": prepared})
                    try:
                        git(repo, "push", "--", "origin", f"{prepared['revision']}:refs/heads/{prepared['branch']}")
                        existing = reconcile(prepared)
                        if not existing or existing.get('revision') != prepared['revision']:
                            raise ValueError('provider head does not match prepared output after branch update')
                    except (ValueError, OSError):
                        atomic_json(record_path, {"status": "ambiguous", "prepared": prepared})
                        raise
                result = {"kind": kind, **existing}
            elif record and record.get("status") in {"publishing", "ambiguous", "published"}:
                raise ValueError("previous publication outcome is ambiguous; no duplicate create attempted")
            else:
                host, project = remote_identity(repo, kind)
                atomic_json(record_path, {"status": "publishing", "prepared": prepared})
                try:
                    git(repo, "push", "--", "origin", f"{prepared['revision']}:refs/heads/{prepared['branch']}")
                    body = prepared["body"] + "\n\n" + prepared["marker"] + "\n"
                    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", prefix="sdlckit-body-", suffix=".md") as stream:
                        stream.write(body)
                        stream.flush()
                        if kind == "github_pr":
                            argv = ["gh", "pr", "create", "--repo", f"{host}/{project}", "--head", prepared["branch"],
                                    "--base", prepared["base"], "--title", prepared["title"], "--body-file", stream.name, "--draft"]
                        else:
                            argv = ["glab", "mr", "create", "--repo", f"https://{host}/{project}",
                                    "--source-branch", prepared["branch"], "--target-branch", prepared["base"],
                                    "--title", prepared["title"], "--description-file", stream.name,
                                    "--draft", "--push=false", "--yes"]
                        command(argv, cwd=repo)
                    found = reconcile(prepared)
                    if not found or found.get('revision') != prepared['revision']:
                        raise ValueError("publication acknowledgement is incomplete; reconcile before retry")
                    result = {"kind": kind, **found}
                except (ValueError, OSError):
                    atomic_json(record_path, {"status": "ambiguous", "prepared": prepared})
                    raise
        atomic_json(record_path, {"status": "published", "prepared": prepared, "result": result})
        return complete(result)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=KINDS)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--work-id", required=True)
    parser.add_argument("--config")
    parser.add_argument("--title", default="")
    parser.add_argument("--body-file")
    parser.add_argument("--base")
    parser.add_argument("--since", help="ancestor commit baseline for exporting committed local changes")
    parser.add_argument("--branch")
    parser.add_argument("--path", action="append")
    parser.add_argument("--output")
    parser.add_argument("--message")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--approve-local", action="store_true")
    parser.add_argument("--approve-external", action="store_true")
    parser.add_argument("--runtime-db")
    parser.add_argument("--run-id")
    args = parser.parse_args(argv)
    try:
        from .config import load_for_target
        config = load_for_target(args.repo, args.config)
        body = ""
        if args.body_file:
            body_path = confined(args.repo, args.body_file)
            if secret_path(body_path) or body_path.stat().st_size > 2 * 1024 * 1024:
                raise ValueError("delivery body file is secret or too large")
            body = body_path.read_text()
        prepared = prepare(args.repo, args.kind, args.work_id, args.title, body, args.base, args.branch, args.path, config, args.since)
        result = prepared if args.dry_run else publish(prepared, config, args.approve_local, args.approve_external,
                                                      args.output, args.message, args.runtime_db, args.run_id)
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, PermissionError, OSError) as exc:
        parser.exit(2, f"delivery: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
