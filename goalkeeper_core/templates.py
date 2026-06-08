"""Contract templates for `init --template NAME`.

A template = a domain + a partial contract overlay merged onto the default
skeleton (and the domain adapter's default_template). Keeps init fast and
domain-appropriate.
"""
from __future__ import annotations

from .adapters import get_adapter
from .contract import default_contract

# name -> (domain, overlay)
TEMPLATES: dict[str, tuple[str, dict]] = {
    "code-refactor": ("code", {
        "goal": {"priority": "high"},
        "validators": [
            {"id": "tests", "type": "command", "command": "npm test", "pass_condition": "exit_zero", "required": True},
            {"id": "typecheck", "type": "command", "command": "npm run typecheck", "pass_condition": "exit_zero", "required": True},
            {"id": "scope", "type": "git_diff", "params": {}, "pass_condition": "no_forbidden_paths_changed", "required": True},
        ],
        "checkpoints": [{"id": "cp1", "description": "behavior preserved; public API unchanged", "evidence_required": "command output", "status": "pending"}],
        "scope": {"forbidden_actions": ["change public behavior", "add production dependencies"]},
    }),
    "bugfix": ("code", {
        "loop": {"mode": "repair_until_pass"},
        "validators": [
            {"id": "regression", "type": "command", "command": "npm test", "pass_condition": "exit_zero", "required": True},
        ],
        "checkpoints": [{"id": "cp1", "description": "failing case now passes; regression test added", "evidence_required": "test output", "status": "pending"}],
    }),
    "research": ("research", {
        "validators": [
            {"id": "report", "type": "file_exists", "params": {"path": "research/report.md"}, "pass_condition": "exists", "required": True},
            {"id": "accept", "type": "human_approval", "pass_condition": "approved:accept", "required": True},
        ],
        "checkpoints": [{"id": "cp1", "description": ">=3 sources per option, one <12 months old", "evidence_required": "source list", "status": "pending"}],
    }),
    "writing": ("writing", {
        "validators": [
            {"id": "draft", "type": "file_exists", "params": {"path": "drafts/draft.md"}, "pass_condition": "exists", "required": True},
            {"id": "review", "type": "human_approval", "pass_condition": "approved:review", "required": True},
        ],
        "checkpoints": [{"id": "cp1", "description": "brief covered; clear CTA; no unsupported claims", "evidence_required": "reviewer note", "status": "pending"}],
    }),
    "recurring-maintenance": ("ops", {
        "loop": {"mode": "scheduled_recurring", "max_turns": 4},
        "risk": {"level": "medium", "external_side_effects": False, "approval_required_before": ["upgrade dependencies"]},
        "validators": [
            {"id": "audit", "type": "command", "command": "npm audit --audit-level=high", "pass_condition": "exit_zero", "required": True},
        ],
        "checkpoints": [{"id": "cp1", "description": "no high-severity advisories, or report filed", "evidence_required": "audit output", "status": "pending"}],
    }),
    "data-quality": ("ops", {
        "risk": {"level": "medium", "external_side_effects": False},
        "validators": [
            {"id": "rowcount", "type": "sql_query", "params": {}, "pass_condition": "rowcount_eq:0", "required": True},
        ],
        "checkpoints": [{"id": "cp1", "description": "anomaly query returns within threshold", "evidence_required": "query result", "status": "pending"}],
    }),
    "incident-review": ("ops", {
        "loop": {"mode": "human_review_loop"},
        "risk": {"level": "high", "external_side_effects": False, "approval_required_before": ["publish postmortem"]},
        "validators": [
            {"id": "postmortem", "type": "file_exists", "params": {"path": "incidents/postmortem.md"}, "pass_condition": "exists", "required": True},
            {"id": "signoff", "type": "human_approval", "pass_condition": "approved:signoff", "required": True},
        ],
        "checkpoints": [{"id": "cp1", "description": "timeline, root cause, action items captured", "evidence_required": "doc link", "status": "pending"}],
    }),
}


def template_names() -> list[str]:
    return list(TEMPLATES.keys())


def build_from_template(name: str, objective: str = "", root=None) -> dict:
    if name not in TEMPLATES:
        raise KeyError(name)
    domain, overlay = TEMPLATES[name]
    state = default_contract(objective, domain=domain, root=root)
    _deep_merge(state, get_adapter(domain).default_template())
    _deep_merge(state, overlay)
    return state


def _deep_merge(base: dict, overlay: dict) -> None:
    for k, v in overlay.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
