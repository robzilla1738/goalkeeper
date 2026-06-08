"""Validator registry: type -> handler dispatch.

Each handler implements `evaluate(spec, ctx) -> ValidatorResult`. Remote types
degrade to "unavailable + manual evidence" rather than importing third-party
drivers, keeping the whole package stdlib-only.
"""
from __future__ import annotations

from .base import EvalContext, Validator, ValidatorResult
from .deferred import (
    GithubCheckValidator,
    HttpCheckValidator,
    SqlQueryValidator,
    TicketStateValidator,
)
from .human import HumanApprovalValidator, RubricValidator
from .local import (
    CommandValidator,
    FileContainsValidator,
    FileExistsValidator,
    GitDiffValidator,
)

REGISTRY: dict[str, Validator] = {
    h.type: h
    for h in (
        CommandValidator(),
        GitDiffValidator(),
        FileExistsValidator(),
        FileContainsValidator(),
        HttpCheckValidator(),
        GithubCheckValidator(),
        TicketStateValidator(),
        SqlQueryValidator(),
        RubricValidator(),
        HumanApprovalValidator(),
    )
}


def known_types() -> list[str]:
    return list(REGISTRY.keys())


def evaluate(spec: dict, ctx: EvalContext) -> ValidatorResult:
    handler = REGISTRY.get(spec.get("type", ""))
    if handler is None:
        return ValidatorResult(None, False, 0, f"unknown validator type: {spec.get('type')!r}")
    return handler.evaluate(spec, ctx)


__all__ = ["REGISTRY", "known_types", "evaluate", "EvalContext", "ValidatorResult"]
