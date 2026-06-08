"""Adapter registry: goal.domain -> Adapter (code is the default fallback)."""
from __future__ import annotations

from .base import Adapter
from .code import CodeAdapter
from .ops import OpsAdapter
from .research import ResearchAdapter
from .writing import WritingAdapter

ADAPTERS: dict[str, Adapter] = {
    a.domain: a for a in (CodeAdapter(), ResearchAdapter(), WritingAdapter(), OpsAdapter())
}


def known_domains() -> list[str]:
    return list(ADAPTERS.keys())


def get_adapter(domain: str | None) -> Adapter:
    return ADAPTERS.get(domain or "code", ADAPTERS["code"])


__all__ = ["Adapter", "ADAPTERS", "known_domains", "get_adapter"]
