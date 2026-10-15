"""Requirements intake with provenance, opt-in CLI/MCP sources and bounded retrieval."""

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import ipaddress
import http.client
import json
import os
from pathlib import Path
import queue
import re
import socket
import ssl
import subprocess
import threading
import time
from urllib.parse import urlparse

from .storage import atomic_json, command, confined, digest, secret_path

MAX_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True)
class SourceDocument:
    kind: str
    ref: str
    revision: str
    retrieved_at: str
    title: str
    body: str
    metadata: dict
    trust: str = "untrusted_evidence"


@dataclass(frozen=True)
class WorkItem:
    schema_version: int
    work_id: str
    title: str
    type: str
    goal: str
    acceptance_criteria: list
    sources: list
    external_references: list
    affected_projects: list
    unknowns: list
    requested_delivery: str


def document(kind, ref, body, title="", revision=None, metadata=None):
    if not isinstance(body, str) or len(body.encode()) > MAX_BYTES:
        raise ValueError("source body is invalid or exceeds retrieval limit")
    return SourceDocument(
        kind=kind, ref=ref, revision=revision or "sha256:" + digest(body),
        retrieved_at=datetime.now(timezone.utc).isoformat(), title=title or ref,
        body=body, metadata=metadata or {},
    )


def public_https(url, allowed_hosts=None):
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("source URLs must use HTTPS without embedded credentials")
    if parsed.port not in (None, 443):
        raise ValueError("source URL port must be 443")
    if allowed_hosts and parsed.hostname not in allowed_hosts:
        raise PermissionError("source URL host is not enabled")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError("source URL host cannot be resolved") from exc
    if any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
        raise PermissionError("private, loopback and link-local URL destinations are forbidden")
    return parsed


def fetch_https(ref, allowed_hosts=None):
    """Pin a validated public address while preserving TLS hostname verification."""
    parsed = public_https(ref, allowed_hosts)
    addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
        raise PermissionError("URL DNS resolution changed to an unauthorized address")
    address = addresses[0][4]
    raw_socket = socket.socket(addresses[0][0], socket.SOCK_STREAM)
    raw_socket.settimeout(30)
    context = ssl.create_default_context()
    connection = http.client.HTTPSConnection(parsed.hostname, timeout=30, context=context)
    try:
        raw_socket.connect(address)
        connection.sock = context.wrap_socket(raw_socket, server_hostname=parsed.hostname)
        target = parsed.path or "/"
        if parsed.query:
            target += "?" + parsed.query
        connection.request("GET", target, headers={"User-Agent": "SDLCkit/2.0", "Accept": "text/plain,text/html,application/json"})
        response = connection.getresponse()
        if 300 <= response.status < 400:
            raise PermissionError("source redirect refused; enable and fetch the destination explicitly")
        if response.status != 200:
            raise ValueError(f"URL source returned HTTP {response.status}")
        data = response.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("URL source exceeds retrieval limit")
        return data.decode("utf-8"), response.getheader("Content-Type", "")
    finally:
        connection.close()
        raw_socket.close()


class MCPSource:
    """Bounded newline-delimited stdio MCP client, with no sampling/elicitation execution."""

    def __init__(self, config):
        self.config = config

    def call(self, capability, arguments):
        tools = self.config.get("tools", {})
        if capability not in {"fetch", "search", "fetch_related"} or capability not in tools:
            raise ValueError(f"connector does not support read capability: {capability}")
        argv = self.config.get("command")
        if isinstance(argv, str):
            argv = [argv] + self.config.get("args", [])
        if not isinstance(argv, list) or not argv or not all(isinstance(x, str) for x in argv):
            raise ValueError("MCP connector command must be a nonempty argv list")
        if Path(argv[0]).name in {"npx", "uvx", "bunx", "pip", "pip3", "npm", "pnpm", "yarn"}:
            raise PermissionError("install the MCP server separately and configure its installed executable; package runners are not launched by intake")
        timeout = min(float(self.config.get("timeout_seconds", 30)), 120)
        preserved = {"PATH", "HOME", "USER", "SHELL", "LANG", "LC_ALL", "TMPDIR", "SYSTEMROOT", "XDG_CONFIG_HOME", "XDG_DATA_HOME"}
        env = {key: value for key, value in os.environ.items() if key in preserved}
        # Environment config names existing variables; literal secrets never enter the manifest.
        env_from = self.config.get("env_from", {})
        if isinstance(env_from, list):
            env_from = {name: name for name in env_from}
        if not isinstance(env_from, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in env_from.items()):
            raise ValueError("env_from must name existing variables as a mapping or string list")
        for key, name in env_from.items():
            if name not in os.environ:
                raise ValueError(f"connector environment variable unavailable: {name}")
            env[key] = os.environ[name]
        try:
            process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=subprocess.DEVNULL, env=env, start_new_session=True)
        except FileNotFoundError as exc:
            raise ValueError("MCP connector executable unavailable") from exc
        messages = queue.Queue(maxsize=64)

        def read():
            try:
                while True:
                    line = process.stdout.readline(MAX_BYTES + 1)
                    if not line:
                        break
                    if len(line) > MAX_BYTES:
                        messages.put_nowait(ValueError("MCP message exceeds retrieval limit"))
                        break
                    messages.put_nowait(json.loads(line))
            except (ValueError, queue.Full) as exc:
                try:
                    messages.put_nowait(exc)
                except queue.Full:
                    pass
            finally:
                try:
                    messages.put_nowait(EOFError())
                except queue.Full:
                    pass

        thread = threading.Thread(target=read, daemon=True)
        thread.start()
        deadline = time.monotonic() + timeout

        def send(payload):
            process.stdin.write((json.dumps({"jsonrpc": "2.0", **payload}) + "\n").encode())
            process.stdin.flush()

        def rpc(number, method, params):
            send({"id": number, "method": method, "params": params})
            while True:
                if time.monotonic() >= deadline:
                    raise ValueError("MCP connector timed out")
                try:
                    reply = messages.get(timeout=max(0.001, deadline - time.monotonic()))
                except queue.Empty as exc:
                    raise ValueError("MCP connector timed out") from exc
                if isinstance(reply, Exception):
                    raise ValueError("MCP connector returned invalid or incomplete output") from reply
                if "method" in reply:
                    if "id" in reply:
                        send({"id": reply["id"], "error": {"code": -32601, "message": "client capability disabled"}})
                    continue
                if reply.get("id") == number:
                    if "error" in reply:
                        raise ValueError("MCP connector reported an error; inspect server locally")
                    return reply.get("result", {})

        try:
            initialized = rpc(1, "initialize", {"protocolVersion": "2025-11-25", "capabilities": {},
                             "clientInfo": {"name": "sdlckit", "version": "2.0.0"}})
            if initialized.get("protocolVersion") not in {"2025-11-25", "2025-06-18", "2024-11-05"}:
                raise ValueError("unsupported MCP protocol version")
            send({"method": "notifications/initialized"})
            available = rpc(2, "tools/list", {}).get("tools", [])
            mapping = tools[capability]
            name = mapping if isinstance(mapping, str) else mapping["name"]
            if name not in {tool["name"] for tool in available}:
                raise ValueError("configured MCP tool is not exposed by the server")
            mapped = dict(mapping.get("arguments", {})) if isinstance(mapping, dict) else {}
            keys = mapping.get("argument_map", {}) if isinstance(mapping, dict) else {}
            mapped.update({keys.get(key, key): value for key, value in arguments.items()})
            result = rpc(3, "tools/call", {"name": name, "arguments": mapped})
            if result.get("isError"):
                raise ValueError("MCP source fetch failed")
            if "structuredContent" in result:
                return result["structuredContent"]
            content = "\n".join(x["text"] for x in result.get("content", []) if x.get("type") == "text")
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return {"body": content}
        finally:
            if process.poll() is None:
                import signal
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
            process.stdin.close()
            process.stdout.close()
            thread.join(timeout=1)


class Intake:
    def __init__(self, config=None, root=None):
        self.config = config or {}
        self.root = Path(root or self.config.get("workspace", {}).get("root", ".")).resolve()

    def provider(self, kind):
        providers = self.config.get("integrations", {})
        item = providers.get(kind)
        if not isinstance(item, dict):
            item = next((x for x in providers.get("custom_mcp", []) if x.get("id") == kind), {})
        if not item.get("enabled", False):
            raise PermissionError(f"requirement integration is disabled: {kind}")
        return item

    def identify(self, ref):
        parsed = urlparse(ref)
        if parsed.scheme == "https":
            if parsed.hostname == "github.com" and re.search(r"/issues/\d+$", parsed.path):
                return "github"
            if "/-/issues/" in parsed.path:
                return "gitlab"
            for kind, item in self.config.get("integrations", {}).items():
                if isinstance(item, dict) and parsed.hostname in item.get("hosts", []):
                    return kind
            return "url"
        if (self.root / ref).is_file():
            return "local_file"
        for kind, item in self.config.get("integrations", {}).items():
            if isinstance(item, dict) and item.get("enabled") and item.get("reference_pattern"):
                if re.fullmatch(item["reference_pattern"], ref):
                    return kind
        raise ValueError("cannot identify requirement; select --source prompt, local_file or an enabled connector")

    def fetch(self, ref, kind=None):
        kind = kind or self.identify(ref)
        enabled = self.config.get("requirements", {}).get("enabled", ["prompt", "local_files"])
        if kind == "prompt":
            if "prompt" not in enabled:
                raise PermissionError("prompt requirements disabled")
            return document(kind, "user-message:" + digest(ref)[:16], ref, ref.splitlines()[0][:120] if ref else "Requirement")
        if kind in {"file", "local_file", "local_files", "repository"}:
            if "local_files" not in enabled:
                raise PermissionError("local-file requirements disabled")
            path = confined(self.root, ref)
            if secret_path(path) or not path.is_file() or path.stat().st_size > MAX_BYTES:
                raise ValueError("source file is secret, missing or too large")
            if path.suffix.lower() == ".pdf":
                body = command(["pdftotext", str(path), "-"], timeout=30).decode("utf-8")
            else:
                body = path.read_text(encoding="utf-8")
            return document("local_file", str(path.relative_to(self.root)), body, path.stem,
                            revision="sha256:" + digest(path.read_bytes()))
        provider = self.provider(kind)
        if provider.get("command"):
            data = MCPSource(provider).call("fetch", {"ref": ref})
        elif kind == "github":
            if ref.startswith("-"):
                raise ValueError("invalid source reference")
            data = json.loads(command(["gh", "issue", "view", ref, "--json", "title,body,url,updatedAt,number"]))
        elif kind == "gitlab":
            if ref.startswith("-"):
                raise ValueError("invalid source reference")
            data = json.loads(command(["glab", "issue", "view", ref, "--output", "json"]))
        elif kind == "url":
            body, content_type = fetch_https(ref, provider.get("hosts"))
            return document(kind, ref, body, metadata={"content_type": content_type})
        else:
            raise ValueError(f"{kind} requires a configured read-only MCP stdio adapter; no capability is fabricated")
        if not isinstance(data, dict):
            raise ValueError("connector must return a SourceDocument object")
        body = data.get("body", data.get("description", ""))
        return document(kind, data.get("url", data.get("web_url", ref)), body,
                        data.get("title", ref), data.get("revision", data.get("updatedAt", data.get("updated_at"))),
                        metadata={"external_id": data.get("number", data.get("iid", data.get("id")))})

    def search(self, kind, query):
        provider = self.provider(kind)
        if provider.get("command"):
            result = MCPSource(provider).call("search", {"query": query})
            if len(json.dumps(result).encode()) > MAX_BYTES:
                raise ValueError("search exceeds retrieval limit")
            return result
        if kind == "github":
            return json.loads(command(["gh", "issue", "list", "--search", query, "--limit", "20", "--json", "number,title,url"]))
        raise ValueError("source does not expose search; configure its MCP read capability")

    def enrich(self, source, max_related=5):
        provider = self.provider(source.kind)
        if not provider.get("command") or "fetch_related" not in provider.get("tools", {}):
            return []
        if not 0 <= max_related <= 20:
            raise ValueError("related source limit must be between 0 and 20")
        result = MCPSource(provider).call("fetch_related", {"ref": source.ref, "limit": max_related})
        refs = result.get("references", []) if isinstance(result, dict) else result
        if not isinstance(refs, list):
            raise ValueError("related-source response must be a bounded reference list")
        return [self.fetch(ref, source.kind) for ref in refs[:max_related]]


def make_work_item(sources, title=None, criteria=None, projects=None, delivery="working_tree", work_id=None):
    if not sources:
        raise ValueError("at least one source is required")
    title = title or sources[0].title
    identity = "\n".join(source.kind + ":" + source.ref for source in sources)
    work_id = work_id or "work-" + digest(identity)[:16]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,100}", work_id):
        raise ValueError("invalid work ID")
    allowed = {"report", "working_tree", "patch", "commit", "local_branch", "github_pr", "gitlab_mr"}
    if delivery not in allowed:
        raise ValueError("unsupported requested delivery")
    item = WorkItem(
        schema_version=1, work_id=work_id, title=title, type="feature", goal=sources[0].body,
        acceptance_criteria=[{"id": f"AC-{i}", "text": text} for i, text in enumerate(criteria or [], 1)],
        sources=[asdict(source) for source in sources],
        external_references=[{"kind": s.kind, "ref": s.ref} for s in sources if s.kind not in {"prompt", "local_file"}],
        affected_projects=projects or [], unknowns=[] if criteria else ["Acceptance criteria require confirmation before execution"],
        requested_delivery=delivery,
    )
    import jsonschema
    schema = json.loads((Path(__file__).resolve().parents[1] / "schemas/work-item-v1.json").read_text())
    try:
        jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(asdict(item))
    except jsonschema.ValidationError as exc:
        raise ValueError(f"invalid WorkItem: {exc.message}") from exc
    return item


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference")
    parser.add_argument("--source")
    parser.add_argument("--root", default=".")
    parser.add_argument("--config")
    parser.add_argument("--title")
    parser.add_argument("--work-id")
    parser.add_argument("--criterion", action="append", default=[])
    parser.add_argument("--project", action="append", default=[])
    parser.add_argument("--delivery", default="working_tree")
    parser.add_argument("--related", type=int, default=0)
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    try:
        from .config import load_for_target
        config = load_for_target(args.root, args.config)
        intake = Intake(config, args.root)
        source = intake.fetch(args.reference, args.source)
        sources = [source] + (intake.enrich(source, args.related) if args.related else [])
        item = asdict(make_work_item(sources, args.title, args.criterion, args.project, args.delivery, args.work_id))
        if args.output:
            output = confined(args.root, args.output)
            if secret_path(output) or output.exists():
                raise ValueError("output must be a new non-secret path inside the workspace")
            atomic_json(output, item)
        print(json.dumps(item, indent=2, ensure_ascii=False))
        return 0
    except (ValueError, PermissionError, OSError) as exc:
        parser.exit(2, f"intake: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
