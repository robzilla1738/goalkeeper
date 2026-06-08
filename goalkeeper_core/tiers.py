"""Verifier-tier (0-6) computation as monotone gates.

0 Claim · 1 Ledger · 2 Artifact · 3 Deterministic · 4 Independent re-run ·
5 Human acceptance · 6 External reality. You can only claim tier N when every
gate up to N holds, so a pure local-code contract correctly tops out at 3-4.
"""
from __future__ import annotations

from .evaluation import checkpoints_with_evidence, scope_clean
from .ledger import ledger_nonempty
from .validators import ValidatorResult


def compute_tier(state: dict, results: list[tuple[dict, ValidatorResult]], changed: list[str], root=None) -> int:
    required = [(v, r) for v, r in results if v.get("required")]

    tier = 0  # a claim always exists

    # Tier 1 (Ledger): required validators were at least recorded + ledger has entries.
    if ledger_nonempty(root) and all(r is not None for _, r in required):
        tier = 1

    # Tier 2 (Artifact): scope clean and met-checkpoints carry evidence.
    if tier == 1 and scope_clean(state, changed) and checkpoints_with_evidence(state):
        tier = 2

    # Tier 3 (Deterministic): all locally-runnable required validators passed,
    # and no required validator is unavailable.
    runnable_required = [(v, r) for v, r in required if r.available]
    none_required_unavailable = not any((v.get("required") and not r.available) for v, r in results)
    if (
        tier == 2
        and runnable_required
        and all(r.passed for _, r in runnable_required)
        and none_required_unavailable
    ):
        tier = 3

    # Tier 4 (Independent re-run): a required validator proved at tier >= 4.
    if tier == 3 and any(r.tier >= 4 and r.passed for _, r in required):
        tier = 4

    # Tier 5 (Human acceptance): a required human/rubric validator passed,
    # or completion was accepted by a named human.
    human_ok = any(r.tier >= 5 and r.passed for _, r in required) or bool(
        state.get("completion", {}).get("accepted_by")
    )
    if tier == 4 and human_ok:
        tier = 5

    # Tier 6 (External reality): a required external validator passed with evidence.
    if tier == 5 and any(r.tier >= 6 and r.passed for _, r in required):
        tier = 6

    return tier
