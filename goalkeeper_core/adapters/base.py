"""Adapter interface: a domain module selected by goal.domain.

Adapters customize templates, expected validator types, and render/verify
presentation without changing Core logic.
"""
from __future__ import annotations


class Adapter:
    domain: str = "base"

    def default_template(self) -> dict:
        """A v2 contract preset (partial; merged onto the default skeleton)."""
        return {}

    def supported_validator_types(self) -> list[str]:
        return ["command", "git_diff", "file_exists", "file_contains"]

    def render_prompt_extras(self, contract: dict) -> str:
        """Domain-specific clauses appended to the /goal prompt."""
        return ""

    def verify_extras(self, contract: dict, results: list) -> list[tuple[str, str]]:
        """Optional extra gate blockers as (code, detail) tuples."""
        return []

    def default_risk(self) -> dict:
        return {"level": "low", "external_side_effects": False}
