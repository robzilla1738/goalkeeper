"""Ops adapter — external side effects, high risk, approval gates."""
from __future__ import annotations

from .base import Adapter


class OpsAdapter(Adapter):
    domain = "ops"

    def default_template(self) -> dict:
        return {
            "loop": {"mode": "watch_until_event", "pause_when": ["needs_human_input", "approval_required"]},
            "risk": {
                "level": "high",
                "external_side_effects": True,
                "approval_required_before": ["send", "publish", "delete", "deploy"],
            },
        }

    def supported_validator_types(self) -> list[str]:
        return ["command", "http_check", "ticket_state", "human_approval"]

    def render_prompt_extras(self, contract: dict) -> str:
        return (
            "Operations may have irreversible external side effects. Do not "
            "send/publish/delete/deploy without a recorded approval."
        )

    def default_risk(self) -> dict:
        return {"level": "high", "external_side_effects": True}
