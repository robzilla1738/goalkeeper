"""Code adapter — the default. Mirrors v1 behavior (git/tests/typecheck/scope)."""
from __future__ import annotations

from .base import Adapter


class CodeAdapter(Adapter):
    domain = "code"

    def supported_validator_types(self) -> list[str]:
        return ["command", "git_diff", "file_exists", "file_contains", "github_check"]

    def render_prompt_extras(self, contract: dict) -> str:
        return (
            "Work turn by turn; run validations through `goalkeeper run` so exit "
            "codes are recorded, and record evidence for each checkpoint."
        )

    def default_risk(self) -> dict:
        return {"level": "low", "external_side_effects": False}
