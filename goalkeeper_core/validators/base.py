"""Validator handler interface and the evaluation context."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ValidatorResult:
    passed: bool | None     # True/False, or None == could not evaluate (deferred)
    available: bool         # could this run in the current environment?
    tier: int               # tier this validator proves WHEN passed (0-6)
    evidence: str           # human/machine-readable proof
    detail: dict = field(default_factory=dict)


@dataclass
class EvalContext:
    root: Path
    base_ref: str
    runs: list[dict]            # the runs.jsonl ledger
    approvals: list[dict]       # state["approvals"]
    changed_files: list[str]    # gitio.changed_files(base_ref)


class Validator:
    """Base handler. Subclasses set `type`/`can_run_locally` and override evaluate."""

    type: str = "base"
    can_run_locally: bool = True
    tier_on_pass: int = 0

    def evaluate(self, spec: dict, ctx: EvalContext) -> ValidatorResult:  # pragma: no cover
        raise NotImplementedError

    def _deferred(self, why: str) -> ValidatorResult:
        return ValidatorResult(passed=None, available=False, tier=self.tier_on_pass, evidence=why)
