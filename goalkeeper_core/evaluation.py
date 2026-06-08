"""Shared validator evaluation used by score, gate, and proof."""
from __future__ import annotations

from pathlib import Path

from .gitio import changed_files
from .ledger import read_runs
from .matching import matches_any
from .validators import EvalContext, ValidatorResult, evaluate


def build_context(state: dict, root: Path, base_override: str | None = None) -> EvalContext:
    base_ref = base_override or state.get("base_ref") or "HEAD"
    return EvalContext(
        root=root,
        base_ref=base_ref,
        runs=read_runs(root),
        approvals=state.get("approvals", []),
        changed_files=changed_files(base_ref, root),
    )


def evaluate_all(state: dict, ctx: EvalContext) -> list[tuple[dict, ValidatorResult]]:
    return [(v, evaluate(v, ctx)) for v in state.get("validators", [])]


def scope_drift(state: dict, changed: list[str]) -> list[str]:
    allowed = state.get("scope", {}).get("allowed_resources", [])
    return [f for f in changed if allowed and not matches_any(f, allowed)]


def forbidden_hits(state: dict, changed: list[str]) -> list[str]:
    forbidden = state.get("scope", {}).get("forbidden_resources", [])
    return [f for f in changed if matches_any(f, forbidden)]


def scope_clean(state: dict, changed: list[str]) -> bool:
    return not scope_drift(state, changed) and not forbidden_hits(state, changed)


def checkpoints_with_evidence(state: dict) -> bool:
    cps = state.get("checkpoints", [])
    for c in cps:
        if c.get("status") == "met" and not c.get("evidence"):
            return False
    return True
