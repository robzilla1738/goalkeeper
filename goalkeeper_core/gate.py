"""Completion gate: the single arbiter of whether a goal is done.

`evaluate_gate` returns the blockers + tier; `complete` is the ONLY writer of
completion.status == "complete", and only when the gate passes.
"""
from __future__ import annotations

from pathlib import Path

from .adapters import get_adapter
from .evaluation import (
    build_context,
    evaluate_all,
    forbidden_hits,
    scope_drift,
)
from .risk import risk_blockers
from .tiers import compute_tier


def evaluate_gate(state: dict, root: Path, base_override: str | None = None) -> dict:
    """Compute the gate verdict for a contract.

    Returns: {verdict, tier, blockers:[(code,detail)], results, changed}.
    """
    ctx = build_context(state, root, base_override)
    results = evaluate_all(state, ctx)
    changed = ctx.changed_files

    blockers: list[tuple[str, str]] = []

    # 1. Required validators.
    for v, r in results:
        if not v.get("required"):
            continue
        vid = v.get("id", "?")
        if not r.available:
            blockers.append(("validator_unavailable", f"{vid}: {r.evidence}"))
        elif r.passed is False:
            blockers.append(("validator_failed", f"{vid}: {r.evidence}"))
        elif r.passed is None:
            blockers.append(("validator_inconclusive", f"{vid}: {r.evidence}"))

    # 2. Checkpoints.
    for cp in state.get("checkpoints", []):
        cid = cp.get("id", "?")
        if cp.get("status") != "met":
            blockers.append(("checkpoint_unmet", cid))
        elif not cp.get("evidence"):
            blockers.append(("checkpoint_no_evidence", cid))

    # 3. Scope / forbidden drift.
    for f in forbidden_hits(state, changed):
        blockers.append(("forbidden_change", f))
    for f in scope_drift(state, changed):
        blockers.append(("scope_drift", f))

    # 4. Risk + approval gates.
    blockers.extend(risk_blockers(state))

    # 5. Adapter-specific extras.
    blockers.extend(get_adapter(state.get("goal", {}).get("domain")).verify_extras(state, results))

    tier = compute_tier(state, results, changed, root)
    verdict = "COMPLETE" if not blockers else "INCOMPLETE"
    return {
        "verdict": verdict,
        "tier": tier,
        "blockers": blockers,
        "results": results,
        "changed": changed,
    }
