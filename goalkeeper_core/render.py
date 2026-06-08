"""Render the contract into goal.md (md), the native /goal string (prompt), or JSON.

goal.md is a *generated artifact* — never hand-edited — which removes the v1
drift between goal.md and state.json.
"""
from __future__ import annotations

import json

from .adapters import get_adapter


def render(state: dict, fmt: str = "md") -> str:
    if fmt == "json":
        return json.dumps(state, indent=2)
    if fmt == "prompt":
        return build_goal_prompt(state)
    return build_goal_md(state)


def _as_prohibition(action: str) -> str:
    a = action.strip().rstrip(".")
    low = a.lower()
    if low.startswith(("do not", "don't", "never", "no ", "avoid")):
        return a
    return "do not " + a


def build_goal_prompt(state: dict) -> str:
    goal = state.get("goal", {})
    scope = state.get("scope", {})
    loop = state.get("loop", {})
    objective = (goal.get("objective") or "<objective>").strip()
    allowed = scope.get("allowed_resources", [])
    validators = state.get("validators", [])

    clause = objective.rstrip(".")
    if allowed:
        clause += " only in " + ", ".join(allowed)
    clause += "."

    done_parts = []
    for v in validators:
        if v.get("type") == "command" and v.get("command"):
            done_parts.append(f"{v['command']} exits 0")
        else:
            done_parts.append(f"{v.get('id', v.get('type'))} passes")
    done_parts.append(".goalkeeper/work_log.md contains evidence for each checkpoint")
    done = "Done means " + ", and ".join(done_parts) + "."

    constraints = [_as_prohibition(fa) for fa in scope.get("forbidden_actions", [])]
    constraints += [f"do not change {fp}" for fp in scope.get("forbidden_resources", [])]
    constraint_str = (" Constraints: " + "; ".join(constraints) + ".") if constraints else ""

    extras = get_adapter(goal.get("domain")).render_prompt_extras(state)
    extras_str = f" {extras}" if extras else ""

    stop = (
        f" Pause if credentials or human input are needed, or after "
        f"{loop.get('max_turns', 12)} turns without all checks passing."
    )
    return clause + " " + done + constraint_str + extras_str + stop


def build_goal_md(state: dict) -> str:
    goal = state.get("goal", {})
    scope = state.get("scope", {})
    risk = state.get("risk", {})
    loop = state.get("loop", {})

    def bullets(items, empty="- (none)"):
        return "\n".join(f"- {i}" for i in items) if items else empty

    val_lines = []
    for v in state.get("validators", []):
        req = "required" if v.get("required") else "optional"
        target = v.get("command") or json.dumps(v.get("params", {}))
        val_lines.append(f"- [{req}] {v.get('id')} ({v.get('type')}): {target} — {v.get('pass_condition')}")
    cp_lines = []
    for c in state.get("checkpoints", []):
        cp_lines.append(f"- [{c.get('status')}] {c.get('id')}: {c.get('description')} — evidence: {c.get('evidence') or '(pending)'}")

    return f"""# Goal Contract (generated — do not edit; edit via `goalkeeper set` then `render`)

## Objective
{goal.get('objective') or '<objective>'}

- Title: {goal.get('title') or '(unset)'}
- Domain: {goal.get('domain', 'code')}  ·  Priority: {goal.get('priority', 'medium')}  ·  Owner: {goal.get('owner') or '(unset)'}

## Allowed scope
{bullets(scope.get('allowed_resources', []))}

## Forbidden
{bullets(scope.get('forbidden_resources', []) + scope.get('forbidden_actions', []))}

## Validators (how "done" is proven)
{chr(10).join(val_lines) if val_lines else '- (none)'}

## Checkpoints
{chr(10).join(cp_lines) if cp_lines else '- (none)'}

## Risk
- level: {risk.get('level', 'low')}  ·  external side effects: {risk.get('external_side_effects', False)}
- approval required before: {', '.join(risk.get('approval_required_before', [])) or '(none)'}

## Loop
- mode: {loop.get('mode')}  ·  max turns: {loop.get('max_turns')}  ·  wall: {loop.get('max_wall_time_minutes')}m  ·  cost: ${loop.get('max_cost_usd')}
"""
