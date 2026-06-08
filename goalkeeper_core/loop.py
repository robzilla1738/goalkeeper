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
    "validator_unavailable",
    "approval_required",
    "sandbox_required",
    "validator_inconclusive",
}

# Modes that never auto-continue inside a session (host scheduler owns re-invocation).
SCHEDULER_MODES = {"scheduled_recurring"}

# Modes that always end a cycle in a pause awaiting a human.
HUMAN_PAUSE_MODES = {"human_review_loop"}


@dataclass
class StopDecision:
    action: str   # "stop" | "pause" | "continue"
    reason: str


def decide_stop(state: dict, root: Path) -> StopDecision:
    completion = state.get("completion", {}).get("status")
    if completion not in ("active", "draft"):
        return StopDecision("stop", "goal is not active")

    g = evaluate_gate(state, root)
    if g["verdict"] == "COMPLETE":
        return StopDecision("stop", f"gate passed (tier {g['tier']}/6); goal complete")

    mode = state.get("loop", {}).get("mode", "goal_until_pass")
    blockers = g["blockers"]
    codes = {c for c, _ in blockers}

    # Pause when any blocker needs human/host intervention, or the mode is human-gated.
    if codes & PAUSE_BLOCKERS or mode in HUMAN_PAUSE_MODES:
        return StopDecision("pause", _pause_reason(mode, blockers))

    if mode in SCHEDULER_MODES:
        return StopDecision("pause", "scheduled_recurring: one cycle done; re-armed by the host scheduler")

    # Budget check (turn budget is always enforced; wall/cost only if host supplies them).
    rt = state.get("loop_runtime", {})
    used = int(rt.get("autocontinue_turns_used", 0))
    budget = int(state.get("loop", {}).get("max_turns", 0))
    if used >= budget:
        return StopDecision("pause", f"turn budget exhausted ({used}/{budget}); pausing for review")

    open_items = "; ".join(f"{c}: {d}" for c, d in blockers[:6]) or "see gate"
    return StopDecision("continue", _continue_reason(mode, open_items))


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
