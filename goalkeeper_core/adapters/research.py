"""Research adapter — coverage + citations, human acceptance for final sign-off."""
from __future__ import annotations

from .base import Adapter


class ResearchAdapter(Adapter):
    domain = "research"

    def default_template(self) -> dict:
        return {
            "loop": {"mode": "research_until_covered"},
            "risk": {"level": "low", "external_side_effects": False},
        }

    def supported_validator_types(self) -> list[str]:
        return ["file_exists", "file_contains", "rubric", "human_approval"]

    def render_prompt_extras(self, contract: dict) -> str:
        return (
            "Cite a concrete source for every claim. Do not contact vendors or "
            "make commitments. Completion is by coverage + human acceptance, not tests."
        )

    def verify_extras(self, contract: dict, results: list) -> list[tuple[str, str]]:
        # Every met checkpoint should reference evidence (a source).
        blockers = []
        for cp in contract.get("checkpoints", []):
            if cp.get("status") == "met" and not cp.get("evidence"):
                blockers.append(("checkpoint_no_source", cp.get("id", "?")))
        return blockers
