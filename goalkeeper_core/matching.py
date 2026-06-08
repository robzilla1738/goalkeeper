"""Glob / path matching for scope checks (ported from the v1 CLI)."""
from __future__ import annotations

import fnmatch


def matches_any(path: str, patterns: list[str]) -> bool:
    for pat in patterns:
        p = pat.strip()
        if not p:
            continue
        # support trailing ** and bare prefixes
        if p.endswith("/**"):
            prefix = p[:-3].rstrip("/")
            if path == prefix or path.startswith(prefix + "/"):
                return True
        if fnmatch.fnmatch(path, p) or path.startswith(p.rstrip("*")):
            return True
    return False
