"""Filesystem layout: locating .goalkeeper/ and its files."""
from __future__ import annotations

from pathlib import Path

GK_DIR = ".goalkeeper"
STATE_FILE = "state.json"
GOAL_FILE = "goal.md"
LOG_FILE = "work_log.md"
PACKETS_FILE = "agent_packets.md"
EVENTS_FILE = "events.jsonl"
RUNS_FILE = "runs.jsonl"
PROOF_MD = "proof.md"
PROOF_JSON = "proof.json"
ARTIFACTS_DIR = "artifacts"


def find_root(start: Path | None = None) -> Path:
    """Nearest ancestor containing a .goalkeeper dir, else the start dir."""
    start = (start or Path.cwd()).resolve()
    for candidate in [start, *start.parents]:
        if (candidate / GK_DIR).is_dir():
            return candidate
    return start


def gk_path(name: str = "", root: Path | None = None) -> Path:
    base = (root or find_root()) / GK_DIR
    return base / name if name else base


def repo_root() -> Path:
    """Directory containing goalkeeper_core/, hosts/, and bin/."""
    return Path(__file__).resolve().parents[1]
