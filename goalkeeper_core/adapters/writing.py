"""Writing adapter — brief/rubric compliance plus human acceptance."""
from __future__ import annotations

from .base import Adapter


class WritingAdapter(Adapter):
    domain = "writing"

    def default_template(self) -> dict:
        return {
            "loop": {"mode": "human_review_loop"},
            "risk": {"level": "low", "external_side_effects": False},
        }

    def supported_validator_types(self) -> list[str]:
        return ["file_exists", "file_contains", "rubric", "human_approval"]

    def render_prompt_extras(self, contract: dict) -> str:
        return (
            "Match the brief and style constraints. Avoid unsupported claims. "
            "Final acceptance requires a named human reviewer."
        )
