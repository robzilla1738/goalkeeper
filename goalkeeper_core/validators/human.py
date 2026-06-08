"""Human-tier validators: human_approval and rubric (tier 5)."""
from __future__ import annotations

from .base import EvalContext, Validator, ValidatorResult


class HumanApprovalValidator(Validator):
    type = "human_approval"
    can_run_locally = True
    tier_on_pass = 5

    def evaluate(self, spec: dict, ctx: EvalContext) -> ValidatorResult:
        what = spec.get("id", "")
        cond = spec.get("pass_condition", "")
        target = what
        if cond.startswith("approved:"):
            target = cond.split(":", 1)[1]
        match = _find_approval(ctx.approvals, target)
        if match:
            return ValidatorResult(
                True, True, self.tier_on_pass,
                f"approved by {match.get('by')} at {match.get('at')}",
                {"approval": match},
            )
        return ValidatorResult(
            False, True, self.tier_on_pass,
            f"awaiting human approval for '{target}' (use `goalkeeper approve {target} --by <name>`)",
        )


class RubricValidator(Validator):
    type = "rubric"
    can_run_locally = True
    tier_on_pass = 5

    def evaluate(self, spec: dict, ctx: EvalContext) -> ValidatorResult:
        # A rubric passes when a reviewer has recorded an approval for it that
        # meets the score threshold (recorded via `goalkeeper approve` with a note).
        what = spec.get("id", "rubric")
        match = _find_approval(ctx.approvals, what)
        if not match:
            criteria = ", ".join(spec.get("params", {}).get("criteria", [])) or "the rubric"
            return ValidatorResult(
                False, True, self.tier_on_pass,
                f"rubric '{what}' not yet scored against: {criteria}",
            )
        return ValidatorResult(
            True, True, self.tier_on_pass,
            f"rubric '{what}' accepted by {match.get('by')}",
            {"approval": match},
        )


def _find_approval(approvals: list[dict], what: str) -> dict | None:
    for a in approvals or []:
        if a.get("what") == what:
            return a
    return None
