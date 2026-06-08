"""Evidence ledgers: runs.jsonl, events.jsonl, work_log.md.

These are the authoritative records the verifier trusts. `run` records a real
exit code (PostToolUse hooks cannot dependably capture exit codes, and don't
fire for non-Bash tools in Codex), so `runs.jsonl` is the source of truth that
the command validator and gate read.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .clock import now
from .paths import LOG_FILE, RUNS_FILE, find_root, gk_path


def append(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(text)


def log(message: str, root: Path | None = None) -> None:
    append(gk_path(LOG_FILE, root), f"\n- [{now()}] {message}\n")


def record_run(cmd: str, exit_code: int, root: Path | None = None) -> None:
    root = root or find_root()
    rec = {"cmd": cmd, "exit": exit_code, "ts": now()}
    append(gk_path(RUNS_FILE, root), json.dumps(rec) + "\n")
    append(gk_path(LOG_FILE, root), f"\n- [{now()}] ran `{cmd}` -> exit {exit_code}\n")


def run_command(cmd: str, root: Path | None = None) -> int:
    """Execute a validation command in the project root and record it."""
    root = root or find_root()
    proc = subprocess.run(cmd, shell=True, cwd=str(root))
    record_run(cmd, proc.returncode, root)
    return proc.returncode


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


def latest_run(cmd: str, runs: list[dict]) -> dict | None:
    """Most recent recorded run whose command matches `cmd` (exact or prefix)."""
    match = None
    for r in runs:
        rc = r.get("cmd", "")
        if rc == cmd or rc.startswith(cmd) or cmd.startswith(rc):
            match = r  # keep the last (file is append-ordered)
    return match


def ledger_nonempty(root: Path | None = None) -> bool:
    return bool(read_runs(root)) or bool(_worklog_evidence(root))


def _worklog_evidence(root: Path | None = None) -> str:
    p = gk_path(LOG_FILE, root)
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8")
