"""The v2 Goal Contract: default skeleton, locking, and amendment history."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from . import SCHEMA_VERSION
from .clock import now
from .gitio import git_head
from .hostenv import detect_host

# Contract sections that are subject to lock + amendment tracking. Runtime
# bookkeeping (loop_runtime, lock, approvals, amendments, timestamps) is not.
CONTRACT_SECTIONS = (
    "goal",
    "scope",
    "validators",
    "checkpoints",
    "loop",
    "risk",
    "evidence",
    "completion",
)

VALID_STATUSES = ("draft", "active", "paused", "complete", "abandoned")


def default_contract(objective: str = "", domain: str = "code", root: Path | None = None) -> dict:
    """A fresh, schema-valid v2 contract skeleton."""
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": now(),
        "updated_at": now(),
        "host": detect_host(),
        "base_ref": git_head(root),
        "goal": {
            "id": _slug(objective),
            "title": "",
            "objective": objective or "",
            "owner": "",
            "domain": domain,
            "priority": "medium",
        },
        "scope": {
            "allowed_resources": [],
            "forbidden_resources": [],
            "allowed_actions": [],
            "forbidden_actions": [],
        },
        "validators": [],   # [{id,type,command|params,pass_condition,required}]
        "checkpoints": [],  # [{id,description,evidence_required,status,evidence}]
        "loop": {
            "mode": "goal_until_pass",
            "max_turns": 12,
            "max_wall_time_minutes": 60,
            "max_cost_usd": 5.0,
            "stop_when": ["all_required_validators_pass", "all_checkpoints_met"],
            "pause_when": [
                "needs_credentials",
                "needs_human_input",
                "validator_unavailable",
                "approval_required",
            ],
        },
        "risk": {
            "level": "low",
            "data_sensitivity": "normal",
            "external_side_effects": False,
            "approval_required_before": [],
        },
        "evidence": {
            "ledger": ".goalkeeper/work_log.md",
            "validation_runs": ".goalkeeper/runs.jsonl",
            "events": ".goalkeeper/events.jsonl",
            "artifacts_dir": ".goalkeeper/artifacts",
        },
        "completion": {
            "status": "draft",
            "accepted_by": None,
            "completed_at": None,
        },
        "loop_runtime": {
            "autocontinue": False,
            "autocontinue_turns_used": 0,
            "max_autocontinue_turns": 4,
        },
        "lock": {"locked": False, "locked_at": None, "hash": None},
        "approvals": [],
        "amendments": [],
    }


def _slug(text: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (text or "goal").lower()).strip("-")[:40] or "goal"
    stamp = now()[:10].replace("-", "")
    return f"g-{stamp}-{base}"


def contract_view(state: dict) -> dict:
    """The portion of state that constitutes the contract (for hashing/diffing)."""
    return {k: state.get(k) for k in CONTRACT_SECTIONS}


def contract_hash(state: dict) -> str:
    blob = json.dumps(contract_view(state), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def is_locked(state: dict) -> bool:
    return bool(state.get("lock", {}).get("locked"))


def lock(state: dict) -> None:
    state.setdefault("lock", {})
    state["lock"].update({"locked": True, "locked_at": now(), "hash": contract_hash(state)})


def unlock(state: dict, reason: str) -> None:
    prev_hash = state.get("lock", {}).get("hash")
    state.setdefault("lock", {})
    state["lock"].update({"locked": False, "locked_at": None})
    state.setdefault("amendments", []).append(
        {"at": now(), "reason": reason, "prev_hash": prev_hash, "new_hash": contract_hash(state)}
    )


def diff_against_lock(state: dict) -> dict[str, Any]:
    """Pending contract changes vs the hash captured at lock time."""
    locked_hash = state.get("lock", {}).get("hash")
    current = contract_hash(state)
    return {
        "locked": is_locked(state),
        "locked_hash": locked_hash,
        "current_hash": current,
        "changed": bool(locked_hash) and locked_hash != current,
    }
