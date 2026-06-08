"""Evidence ledgers: runs.jsonl, events.jsonl, work_log.md.

These are the authoritative records the verifier trusts. `run` records a real
exit code (PostToolUse hooks cannot dependably capture exit codes, and don't
fire for non-Bash tools in Codex), so `runs.jsonl` is the source of truth that
the command validator and gate read.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from .clock import now
from .paths import ARTIFACTS_DIR, LOG_FILE, RUNS_FILE, find_root, gk_path

DEFAULT_OUTPUT_LIMIT_BYTES = 65536


def append(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(text)


def log(message: str, root: Path | None = None) -> None:
    append(gk_path(LOG_FILE, root), f"\n- [{now()}] {message}\n")


def _output_limit() -> int:
    raw = os.environ.get("GOALKEEPER_RUN_OUTPUT_LIMIT_BYTES")
    if not raw:
        return DEFAULT_OUTPUT_LIMIT_BYTES
    try:
        return max(0, int(raw))
    except ValueError:
        return DEFAULT_OUTPUT_LIMIT_BYTES


def record_run(cmd: str, exit_code: int, root: Path | None = None, **metadata) -> None:
    root = root or find_root()
    rec = {"cmd": cmd, "exit": exit_code, "ts": now()}
    rec.update({k: v for k, v in metadata.items() if v is not None})
    append(gk_path(RUNS_FILE, root), json.dumps(rec) + "\n")
    append(gk_path(LOG_FILE, root), f"\n- [{now()}] ran `{cmd}` -> exit {exit_code}\n")


def _capture_chunk(buf: bytearray, data: bytes, limit: int) -> bool:
    if not data:
        return False
    remaining = limit - len(buf)
    if remaining > 0:
        buf.extend(data[:remaining])
    return len(data) > max(remaining, 0)


def _pump(pipe, dest, capture: bytearray, limit: int, truncated: dict, key: str) -> None:
    try:
        for chunk in iter(lambda: pipe.read(8192), b""):
            if not chunk:
                break
            dest.write(chunk)
            dest.flush()
            if _capture_chunk(capture, chunk, limit):
                truncated[key] = True
    finally:
        pipe.close()


def _write_artifact(root: Path, run_id: str, stream: str, data: bytes, truncated: bool, limit: int) -> str | None:
    if not data and not truncated:
        return None
    rel = f"{ARTIFACTS_DIR}/runs/{run_id}-{stream}.log"
    path = gk_path(rel, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = b""
    if truncated:
        suffix = f"\n[goalkeeper] output truncated at {limit} bytes\n".encode("utf-8")
    path.write_bytes(data + suffix)
    return f".goalkeeper/{rel}"


def run_command(cmd: str, root: Path | None = None) -> int:
    """Execute a validation command, stream output, and record bounded proof."""
    root = root or find_root()
    limit = _output_limit()
    run_id = uuid.uuid4().hex[:12]
    start = time.monotonic()
    stdout = bytearray()
    stderr = bytearray()
    truncated = {"stdout": False, "stderr": False}
    proc = subprocess.Popen(
        cmd,
        shell=True,
        cwd=str(root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert proc.stdout is not None
    assert proc.stderr is not None
    out_thread = threading.Thread(
        target=_pump,
        args=(proc.stdout, sys.stdout.buffer, stdout, limit, truncated, "stdout"),
        daemon=True,
    )
    err_thread = threading.Thread(
        target=_pump,
        args=(proc.stderr, sys.stderr.buffer, stderr, limit, truncated, "stderr"),
        daemon=True,
    )
    out_thread.start()
    err_thread.start()
    exit_code = proc.wait()
    out_thread.join()
    err_thread.join()
    duration_ms = round((time.monotonic() - start) * 1000)
    stdout_artifact = _write_artifact(root, run_id, "stdout", bytes(stdout), truncated["stdout"], limit)
    stderr_artifact = _write_artifact(root, run_id, "stderr", bytes(stderr), truncated["stderr"], limit)
    record_run(
        cmd,
        exit_code,
        root,
        id=run_id,
        cwd=str(root),
        duration_ms=duration_ms,
        stdout_artifact=stdout_artifact,
        stderr_artifact=stderr_artifact,
        stdout_truncated=truncated["stdout"],
        stderr_truncated=truncated["stderr"],
        output_limit_bytes=limit,
    )
    return exit_code


def read_runs(root: Path | None = None) -> list[dict]:
    p = gk_path(RUNS_FILE, root)
    if not p.exists():
        return []
    runs: list[dict] = []
    for ln in p.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            runs.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return runs


def latest_run(cmd: str, runs: list[dict], allow_prefix: bool = False) -> dict | None:
    """Most recent recorded run whose command matches `cmd`.

    Matching is exact by default. Prefix matching is available only for
    validators that explicitly opt in.
    """
    match = None
    for r in runs:
        rc = r.get("cmd", "")
        if rc == cmd or (allow_prefix and (rc.startswith(cmd) or cmd.startswith(rc))):
            match = r  # keep the last (file is append-ordered)
    return match


def ledger_nonempty(root: Path | None = None) -> bool:
    return bool(read_runs(root)) or bool(_worklog_evidence(root))


def _worklog_evidence(root: Path | None = None) -> str:
    p = gk_path(LOG_FILE, root)
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8")
