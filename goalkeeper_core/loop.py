"""Loop-mode semantics and the Stop-hook decision engine.

`decide_stop` is the single place that decides, given a contract and its current
evidence, whether the host should stop, pause, or continue. It reuses the gate
so the loop never lets the agent stop while required blockers remain (and budget
is left), and never pushes past a passing gate.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .gate import evaluate_gate

# Blocker codes that mean "a human/host must intervene" -> pause, not continue.
PAUSE_BLOCKERS = {
    "base_ref_missing",
    "checkpoint_missing",
    "contract_invalid",
    "contract_not_active",
    "objective_missing",
    "objective_unbounded",
    "validator_unavailable",
    "approval_required",
    "required_validator_missing",
    "sandbox_required",
    "scope_missing",
    "validator_missing",
}

# Modes that never auto-continue inside a session (host scheduler owns re-invocation).
SCHEDULER_MODES = {"scheduled_recurring"}

# Modes that always end a cycle in a pause awaiting a human.
HUMAN_PAUSE_MODES = {"human_review_loop"}


@dataclass
class StopDecision:
    action: str   # "stop" | "pause" | "continue"
    reason: str
    gate: dict | None = None   # the gate verdict this decision was based on (if any)


def requires_human_signoff(state: dict) -> bool:
    """True if completion must be accepted by a named human, not auto-recorded.

    High/critical risk, an explicit human_approval/rubric required validator, or
    a human_review_loop mode all mean a person owns the final acceptance.
    """
    risk = state.get("risk", {})
    if isinstance(risk, dict) and risk.get("level") in ("high", "critical"):
        return True
    for v in state.get("validators", []):
        if isinstance(v, dict) and v.get("required") and v.get("type") in ("human_approval", "rubric"):
            return True
    return state.get("loop", {}).get("mode") in HUMAN_PAUSE_MODES


def decide_stop(state: dict, root: Path) -> StopDecision:
    completion = state.get("completion", {}).get("status")
    if completion not in ("active", "draft"):
        return StopDecision("stop", "goal is not active")

    g = evaluate_gate(state, root)
    if g["verdict"] == "COMPLETE":
        return StopDecision("stop", f"gate passed (tier {g['tier']}/6); goal complete", gate=g)

    mode = state.get("loop", {}).get("mode", "goal_until_pass")
    blockers = g["blockers"]
    codes = {c for c, _ in blockers}

    # Pause when any blocker needs human/host intervention, or the mode is human-gated.
    if codes & PAUSE_BLOCKERS or mode in HUMAN_PAUSE_MODES:
        return StopDecision("pause", _pause_reason(mode, blockers), gate=g)

    if mode in SCHEDULER_MODES:
        return StopDecision("pause", "scheduled_recurring: one cycle done; re-armed by the host scheduler", gate=g)

    # Budget check (turn budget is always enforced; wall/cost only if host supplies them).
    rt = state.get("loop_runtime", {})
    used = int(rt.get("autocontinue_turns_used", 0))
    budget = int(state.get("loop", {}).get("max_turns", 0))
    if used >= budget:
        return StopDecision("pause", f"turn budget exhausted ({used}/{budget}); pausing for review", gate=g)

    open_items = "; ".join(f"{c}: {d}" for c, d in blockers[:6]) or "see gate"
    return StopDecision("continue", _continue_reason(mode, open_items), gate=g)


def _pause_reason(mode: str, blockers: list[tuple[str, str]]) -> str:
    items = "; ".join(f"{c}: {d}" for c, d in blockers) or "human input"
    return (
        f"[Goalkeeper] Pausing ({mode}). Needs human/host intervention: {items}. "
        "Record evidence/approvals, then resume."
    )


def _continue_reason(mode: str, open_items: str) -> str:
    lead = {
        "repair_until_pass": "Fix the failing validators first.",
        "research_until_covered": "Continue until coverage checkpoints are met with sources.",
        "watch_until_event": "Keep watching until the stop condition fires.",
        "multi_agent_packet_loop": "Continue until all packets reconcile.",
    }.get(mode, "Continue working inside the allowed scope.")
    return (
        f"[Goalkeeper] Goal not yet complete. {lead} Open blockers: {open_items}. "
        "Run validations through `goalkeeper run` and record evidence in "
        ".goalkeeper/work_log.md. Stop if you need credentials or human input."
    )
