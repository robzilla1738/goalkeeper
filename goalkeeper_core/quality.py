"""Shared contract-quality checks for doctor and the completion gate."""
from __future__ import annotations

from dataclasses import dataclass
import re

from . import SCHEMA_VERSION
from .schema import validate
from .state import get_path

PLACEHOLDER_OBJECTIVES = {
    "make it better",
    "make better",
    "make this better",
    "improve",
    "improve it",
    "improve this",
    "clean up",
    "clean up code",
    "fix stuff",
    "do stuff",
    "etc",
    "as needed",
}
LOW_INFORMATION_TERMS = {
    "stuff",
    "things",
    "thing",
    "whatever",
}
GENERIC_TARGET_TERMS = {
    "app",
    "auth",
    "bug",
    "bugs",
    "code",
    "files",
    "issue",
    "issues",
    "module",
    "modules",
    "project",
    "repo",
    "src",
    "system",
    "ui",
}


@dataclass(frozen=True)
class QualityCheck:
    name: str
    ok: bool
    detail: str = ""
    blocker: str = ""


def contract_quality_checks(state: dict, require_active: bool = False) -> list[QualityCheck]:
    """Return the contract checks that must pass before work can be accepted.

    `doctor` calls this with `require_active=False` because the documented setup
    flow runs doctor before activation. `gate` uses `require_active=True`.
    """
    errors = validate(state, strict=True)
    obj = (get_path(state, "goal.objective") or "").strip()
    vals = state.get("validators", [])
    validators = vals if isinstance(vals, list) else []
    has_required = any(isinstance(v, dict) and v.get("required") for v in validators)
    has_scope = bool(get_path(state, "scope.allowed_resources")) or bool(
        get_path(state, "scope.forbidden_resources")
    )
    raw_checkpoints = state.get("checkpoints", [])
    checkpoints = raw_checkpoints if isinstance(raw_checkpoints, list) else []
    completion = state.get("completion", {})
    status = completion.get("status") if isinstance(completion, dict) else None
    bounded = _objective_is_bounded(obj)

    checks = [
        QualityCheck(
            f"contract validates (schema v{SCHEMA_VERSION}, strict)",
            not errors,
            "" if not errors else f"{len(errors)} error(s)",
            "contract_invalid",
        ),
        QualityCheck("objective set", bool(obj), obj[:60], "objective_missing"),
        QualityCheck(
            "objective is bounded",
            bounded,
            "" if bounded else "contains vague language",
            "objective_unbounded",
        ),
        QualityCheck("validators present", bool(validators), f"{len(validators)}", "validator_missing"),
        QualityCheck("at least one required validator", has_required, "", "required_validator_missing"),
        QualityCheck("scope boundaries present", has_scope, "", "scope_missing"),
        QualityCheck("at least one checkpoint", bool(checkpoints), "", "checkpoint_missing"),
        QualityCheck(
            "diff baseline captured",
            bool(state.get("base_ref")),
            (state.get("base_ref") or "")[:12],
            "",
        ),
    ]
    if require_active:
        checks.insert(
            0,
            QualityCheck(
                "contract active",
                status in ("active", "complete"),
                status or "(unset)",
                "contract_not_active",
            ),
        )
    return checks


def _objective_is_bounded(objective: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", " ", objective.lower()).strip()
    if not normalized or normalized in PLACEHOLDER_OBJECTIVES:
        return False
    tokens = normalized.split()
    if any(token in LOW_INFORMATION_TERMS for token in tokens):
        return False
    if "better" in tokens and len(tokens) <= 3:
        return False
    if tokens[:2] == ["clean", "up"]:
        return _has_concrete_target(tokens[2:])
    if tokens[0] in {"fix", "improve", "make"}:
        return _has_concrete_target(tokens[1:])
    return True


def _has_concrete_target(tokens: list[str]) -> bool:
    return len(tokens) >= 2 and not all(token in GENERIC_TARGET_TERMS for token in tokens)


def failed_quality_blockers(state: dict, require_active: bool = True) -> list[tuple[str, str]]:
    blockers: list[tuple[str, str]] = []
    for check in contract_quality_checks(state, require_active=require_active):
        if check.ok:
            continue
        if not check.blocker:
            continue
        blockers.append((check.blocker or "contract_quality_failed", check.detail or check.name))
    return blockers
