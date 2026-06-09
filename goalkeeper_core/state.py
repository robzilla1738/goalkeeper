"""Canonical state.json I/O and nested (dotted-path) field access.

state.json is the single source of truth. goal.md is a *rendered* view of it
(see render.py) and must never be hand-edited. All structured reads/writes go
through here so the CLI and the hook share one implementation.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .clock import now
from .paths import STATE_FILE, find_root, gk_path


def load_state(root: Path | None = None) -> dict:
    p = gk_path(STATE_FILE, root)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StateError(f"state.json is not valid JSON: {exc}") from exc


def save_state(state: dict, root: Path | None = None) -> None:
    p = gk_path(STATE_FILE, root)
    p.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = now()
    p.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


class StateError(Exception):
    """Raised for malformed state or illegal field operations."""


def get_path(state: dict, dotted: str) -> Any:
    """Read a nested value by dotted path, e.g. 'goal.objective'."""
    cur: Any = state
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def set_path(state: dict, dotted: str, value: Any) -> None:
    """Write a nested value by dotted path, creating intermediate dicts."""
    parts = dotted.split(".")
    cur = state
    for part in parts[:-1]:
        nxt = cur.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[part] = nxt
        cur = nxt
    cur[parts[-1]] = value


# Leaf fields whose values coerce from the CLI string into a list/int/float/bool.
LIST_FIELDS = {
    "scope.allowed_resources",
    "scope.forbidden_resources",
    "scope.allowed_actions",
    "scope.forbidden_actions",
    "loop.stop_when",
    "loop.pause_when",
    "risk.approval_required_before",
}
INT_FIELDS = {"loop.max_turns", "loop.max_wall_time_minutes"}
FLOAT_FIELDS = {"loop.max_cost_usd"}
BOOL_FIELDS = {
    "risk.external_side_effects",
    "loop_runtime.autocontinue",
    "loop.enforce",
    "loop.auto_complete",
}


def coerce(dotted: str, raw: str) -> Any:
    if dotted in LIST_FIELDS:
        return [v.strip() for v in raw.split(",") if v.strip()]
    if dotted in INT_FIELDS:
        return int(raw)
    if dotted in FLOAT_FIELDS:
        return float(raw)
    if dotted in BOOL_FIELDS:
        return raw.lower() in ("1", "true", "yes", "on")
    return raw
