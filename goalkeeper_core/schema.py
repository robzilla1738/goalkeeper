"""Hand-rolled structural validator for the v2 Goal Contract.

We publish a real JSON Schema at schema/goalkeeper.contract.schema.json for
external tooling, but enforce it in-process with explicit checks here: fewer
lines than a JSON-Schema interpreter, far better error messages, and zero
third-party dependencies. `validate(strict=True)` additionally enforces
cross-field rules the JSON Schema can't easily express.
"""
from __future__ import annotations

from typing import Any

from .adapters import known_domains
from .validators import known_types

PRIORITIES = ("low", "medium", "high", "critical")
RISK_LEVELS = ("low", "medium", "high", "critical")
CHECKPOINT_STATUSES = ("pending", "met", "blocked")
COMPLETION_STATUSES = ("draft", "active", "paused", "complete", "abandoned")
LOOP_MODES = (
    "goal_until_pass",
    "repair_until_pass",
    "research_until_covered",
    "watch_until_event",
    "scheduled_recurring",
    "human_review_loop",
    "multi_agent_packet_loop",
)


def validate(state: dict, strict: bool = False) -> list[str]:
    """Return a list of human-readable errors; empty list == valid."""
    e: list[str] = []
    if state.get("schema_version") != 2:
        e.append("schema_version must be 2")

    _require_obj(state, "goal", e)
    goal = state.get("goal", {})
    if isinstance(goal, dict):
        for f in ("id", "title", "objective", "owner", "domain", "priority"):
            if f not in goal:
                e.append(f"goal.{f} is required")
        if goal.get("priority") not in PRIORITIES:
            e.append(f"goal.priority must be one of {PRIORITIES}")
        if goal.get("domain") and goal["domain"] not in known_domains():
            e.append(f"goal.domain '{goal.get('domain')}' is not a registered adapter {tuple(known_domains())}")

    _require_obj(state, "scope", e)
    scope = state.get("scope", {})
    if isinstance(scope, dict):
        for f in ("allowed_resources", "forbidden_resources", "allowed_actions", "forbidden_actions"):
            if not isinstance(scope.get(f, []), list):
                e.append(f"scope.{f} must be a list")

    _validate_validators(state.get("validators"), e)
    _validate_checkpoints(state.get("checkpoints"), e)
    _validate_loop(state.get("loop"), e)
    _validate_risk(state.get("risk"), e)

    _require_obj(state, "evidence", e)
    comp = state.get("completion", {})
    if not isinstance(comp, dict) or "status" not in comp:
        e.append("completion.status is required")
    elif comp.get("status") not in COMPLETION_STATUSES:
        e.append(f"completion.status must be one of {COMPLETION_STATUSES}")

    if strict:
        e.extend(_strict_rules(state))
    return e


def _require_obj(state: dict, key: str, e: list[str]) -> None:
    if not isinstance(state.get(key), dict):
        e.append(f"{key} is required and must be an object")


def _validate_validators(validators: Any, e: list[str]) -> None:
    if not isinstance(validators, list):
        e.append("validators must be a list")
        return
    seen = set()
    for i, v in enumerate(validators):
        if not isinstance(v, dict):
            e.append(f"validators[{i}] must be an object")
            continue
        vid = v.get("id")
        if not vid:
            e.append(f"validators[{i}].id is required")
        elif vid in seen:
            e.append(f"validators[{i}].id '{vid}' is duplicated")
        else:
            seen.add(vid)
        if v.get("type") not in known_types():
            e.append(f"validators[{i}].type must be one of {tuple(known_types())}")
        if "pass_condition" not in v:
            e.append(f"validators[{i}].pass_condition is required")
        if not isinstance(v.get("required"), bool):
            e.append(f"validators[{i}].required must be a boolean")
        if v.get("type") == "command" and not v.get("command"):
            e.append(f"validators[{i}] of type command requires a 'command'")


def _validate_checkpoints(cps: Any, e: list[str]) -> None:
    if not isinstance(cps, list):
        e.append("checkpoints must be a list")
        return
    seen = set()
    for i, c in enumerate(cps):
        if not isinstance(c, dict):
            e.append(f"checkpoints[{i}] must be an object")
            continue
        cid = c.get("id")
        if not cid:
            e.append(f"checkpoints[{i}].id is required")
        elif cid in seen:
            e.append(f"checkpoints[{i}].id '{cid}' is duplicated")
        else:
            seen.add(cid)
        if "description" not in c:
            e.append(f"checkpoints[{i}].description is required")
        if c.get("status") not in CHECKPOINT_STATUSES:
            e.append(f"checkpoints[{i}].status must be one of {CHECKPOINT_STATUSES}")


def _validate_loop(loop: Any, e: list[str]) -> None:
    if not isinstance(loop, dict):
        e.append("loop is required and must be an object")
        return
    if loop.get("mode") not in LOOP_MODES:
        e.append(f"loop.mode must be one of {LOOP_MODES}")
    if not isinstance(loop.get("max_turns"), int) or loop.get("max_turns", 0) <= 0:
        e.append("loop.max_turns must be a positive integer")
    for arr in ("stop_when", "pause_when"):
        if not isinstance(loop.get(arr, []), list):
            e.append(f"loop.{arr} must be a list")


def _validate_risk(risk: Any, e: list[str]) -> None:
    if not isinstance(risk, dict):
        e.append("risk is required and must be an object")
        return
    if risk.get("level") not in RISK_LEVELS:
        e.append(f"risk.level must be one of {RISK_LEVELS}")
    if not isinstance(risk.get("external_side_effects"), bool):
        e.append("risk.external_side_effects must be a boolean")
    if not isinstance(risk.get("approval_required_before", []), list):
        e.append("risk.approval_required_before must be a list")


def _strict_rules(state: dict) -> list[str]:
    e: list[str] = []
    validators = state.get("validators", []) or []
    if not any(v.get("required") for v in validators if isinstance(v, dict)):
        e.append("strict: at least one validator must be required:true")

    risk = state.get("risk", {}) or {}
    if risk.get("level") in ("high", "critical"):
        has_human = any(
            isinstance(v, dict) and v.get("type") in ("human_approval", "rubric")
            for v in validators
        )
        if not has_human and not risk.get("approval_required_before"):
            e.append(
                "strict: high/critical risk requires a human_approval/rubric validator "
                "or a non-empty risk.approval_required_before"
            )

    scope = state.get("scope", {}) or {}
    allowed_actions = set(scope.get("allowed_actions", []) or [])
    for what in risk.get("approval_required_before", []) or []:
        if allowed_actions and what not in allowed_actions:
            e.append(f"strict: approval_required_before '{what}' is not in scope.allowed_actions")

    loop = state.get("loop", {}) or {}
    if loop.get("mode") == "watch_until_event" and not loop.get("pause_when"):
        e.append("strict: watch_until_event requires at least one loop.pause_when event")
    return e
