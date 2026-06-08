"""Risk classes and approval gates."""
from __future__ import annotations

from .clock import now


def find_approval(approvals: list[dict], what: str) -> dict | None:
    for a in approvals or []:
        if a.get("what") == what:
            return a
    return None


def has_human_acceptance(state: dict) -> bool:
    if state.get("completion", {}).get("accepted_by"):
        return True
    return bool(state.get("approvals"))


def risk_blockers(state: dict) -> list[tuple[str, str]]:
    """Approval/risk gate blockers as (code, detail) tuples."""
    out: list[tuple[str, str]] = []
    risk = state.get("risk", {}) or {}
    approvals = state.get("approvals", [])
    lvl = risk.get("level", "low")

    if lvl in ("high", "critical") and not has_human_acceptance(state):
        out.append(("approval_required", f"{lvl} risk requires human approval"))

    if risk.get("external_side_effects") and not find_approval(approvals, "external_side_effects"):
        out.append(("approval_required", "external side effects require approval"))

    for what in risk.get("approval_required_before", []) or []:
        if not find_approval(approvals, what):
            out.append(("approval_required", f"action '{what}' requires approval"))

    if lvl == "critical" and not (state.get("risk", {}) or {}).get("sandbox_declared"):
        out.append(("sandbox_required", "critical risk requires an explicit sandbox/permissions declaration"))

    return out


def record_approval(state: dict, what: str, by: str, note: str = "") -> dict:
    entry = {"what": what, "by": by, "at": now(), "note": note}
    state.setdefault("approvals", []).append(entry)
    return entry
