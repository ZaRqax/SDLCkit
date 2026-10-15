"""Small durable-file and subprocess primitives used by source/delivery adapters."""

import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time


def digest(value):
    if isinstance(value, str):
        value = value.encode()
    return hashlib.sha256(value).hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".sdlc-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)


@contextlib.contextmanager
def exclusive(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def command(argv, cwd=None, stdin=None, timeout=60, allowed=(0,), max_bytes=16 * 1024 * 1024):
    """Execute an argv without a shell; never expose provider stderr or credentials."""
    with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors, tempfile.TemporaryFile() as input_file:
        if stdin is not None:
            input_file.write(stdin)
            input_file.seek(0)
        try:
            process = subprocess.Popen(
                argv, cwd=cwd, stdin=input_file, stdout=output, stderr=errors, start_new_session=True,
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GH_PROMPT_DISABLED": "1"},
            )
        except FileNotFoundError as exc:
            raise ValueError(f"required executable is unavailable: {argv[0]}") from exc
        start = time.monotonic()
        failure = None
        while process.poll() is None:
            if time.monotonic() - start > timeout:
                failure = "timed out; reconcile external state before retrying"
            elif output.tell() > max_bytes or errors.tell() > max_bytes:
                failure = "exceeded output limit"
            if failure:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                break
            time.sleep(0.01)
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        if failure:
            raise ValueError(f"{argv[0]} {failure}")
        if process.returncode not in allowed:
            raise ValueError(f"{argv[0]} failed with exit code {process.returncode}; check authentication/capability locally")
        if output.tell() > max_bytes or errors.tell() > max_bytes:
            raise ValueError(f"{argv[0]} exceeded output limit")
        output.seek(0)
        return output.read(max_bytes)


def confined(root, path):
    root = Path(root).resolve()
    path = Path(path)
    resolved = (root / path).resolve() if not path.is_absolute() else path.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("path escapes the authorized root")
    return resolved


def secret_path(path):
    from .policy import secret_path as protected
    name = Path(path).name.lower()
    return (".git" in Path(path).parts or protected("/" + str(path).lstrip("/"))
            or name in {"credentials", "secrets.json", "token.json"}
            or name.endswith((".pem", ".key", ".p12", ".pfx")))
